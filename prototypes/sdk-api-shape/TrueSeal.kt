// PROTOTYPE — throwaway API sketch for trueseal-roadmap#12. Not compiled, not shipped.
// Package: dev.trueseal.sync. Every sketch file has the same sections in the same order.

// @section setup
import dev.trueseal.sync.*

val relay = RelayAddress.parse("trueseal://9f3ac1…e07b@relay.example.com")
// Same address, typed form. The ports default to 7700 (receive) and 7701 (push).
val sameRelay = RelayAddress(host = "relay.example.com",
                             publicKey = relayKeyHex,
                             receivePort = 7700, pushPort = 7701)

val trueseal = TrueSeal.open(                   // suspend
    relay = relay,
    storage = Storage.android(context),         // or Storage.directory(File)
    namespace = "default",                      // optional
    maxPayloadBytes = null,                     // optional: lower than 61_440 only
)
// open() returns straight away. It connects in the background; send() works at once.

// @section lifecycle
trueseal.close()            // Closeable. Stops the connection and handlers. The outbox persists.
// After close(), every call throws TrueSealException.Closed.

// @section receive
// Registering the message handler starts receiving. There is exactly one handler.
// The handler is awaited: returning acks the message; throwing retries it (5 tries).
val sub = trueseal.onMessage { message ->     // suspend (Message) -> Unit
    db.save(message.body, message.id)          // Message.body: ByteArray
    println("from ${message.from.name}")       // Message.from: Member
}
sub.cancel()                // pauses receiving until a handler is registered again

// @section send
val id: MessageId = trueseal.send("hello".encodeToByteArray())   // suspend
// Returns once the message is in the durable outbox, never after delivery.
// Throws PayloadTooLarge(max) at once for bodies over the limit.

// @section status
trueseal.status        // StateFlow<GroupStatus>: NotJoined | PendingJoin | Member | Leaving
trueseal.me            // Member(id, name) for this device
trueseal.members       // StateFlow<List<Member>>: everyone else in the group
trueseal.connection    // StateFlow<Connection>: Connecting | Connected | Disconnected
                       //   | RelayVersionUnsupported(min, max)

// @section admit
// On a device that's already in the group, or that starts a new one:
val token: String = trueseal.startPairing()   // show as QR / copyable text
// Join requests arrive as events (see Events):
//   is TrueSealEvent.JoinRequest -> event.request   // JoinRequest(id, name)
trueseal.accept(request)            // suspend; single use: the window closes after it
trueseal.cancelPairing()            // closes the window; unaccepted requests vanish
// There is no reject: a request you don't accept never gets an answer.

// @section join
// On the new device:
trueseal.join(token)           // suspend; status → PendingJoin (this survives restarts)
trueseal.cancelJoin()          // status → NotJoined
// Once admitted: StatusChanged(Member, reason = Joined)

// @section membership
trueseal.remove(member.id)     // suspend; any member may remove any other member
trueseal.leave()               // suspend; status → Leaving, then NotJoined(Left)
// A removed or leaving device gets wiped and a fresh identity automatically.
// The same TrueSeal object stays usable and can pair again.

// @section destroy
// PROVISIONAL: semantics are being decided in trueseal-roadmap#10.
trueseal.destroyGroup()        // → StatusChanged(NotJoined, reason = Destroyed)

// @section events
val events = trueseal.onEvent { event ->         // any number of listeners
    when (event) {
        is TrueSealEvent.StatusChanged -> {}      // reason: Created | Joined
                                                  //   | Left | Removed | Destroyed
        is TrueSealEvent.MembersChanged -> {}     // render the list; don't diff events
        is TrueSealEvent.JoinRequest -> {}
        is TrueSealEvent.ConnectionChanged -> {}
        is TrueSealEvent.AdmissionDropped -> {}   // a re-applied admission hit 32
    }
}
// Events raised before the first listener is registered are buffered and replayed.

// @section issues
val issues = trueseal.onDeliveryIssue { issue ->  // optional. Ignoring it is safe.
    when (issue) {
        is DeliveryIssue.Unreadable -> {}                 // couldn't decrypt, verify or parse
        is DeliveryIssue.Unauthorized -> {}               // not from a current member
        is DeliveryIssue.HeldForUpgrade -> {}             // newer End-to-End Version
        is DeliveryIssue.HandlerGaveUp -> {}              // (id, error): threw 5 times
        is DeliveryIssue.SendFailed -> {}                 // (id, reason): TooLarge | Malformed | Expired
        is DeliveryIssue.UndeliverableAfterUpgrade -> {}  // (ids)
    }
}

// @section errors
sealed class TrueSealException(message: String) : Exception(message) {
    class InvalidRelayAddress(val reason: String)
    class InvalidNamespace(val reason: String)
    class Storage(val reason: String)
    object Closed
    class NotMember(val status: GroupStatus)
    object AlreadyInGroup
    object InvalidPairingToken
    object PairingClosed
    class GroupFull(val max: Int)
    object MemberNotFound
    class PayloadTooLarge(val max: Int)
    object MessageHandlerAlreadySet
}

// @section version
TrueSeal.info.sdkVersion          // "0.3.0"
TrueSeal.info.transportVersion    // 1
TrueSeal.info.endToEndVersion     // 1
TrueSeal.MAX_PAYLOAD_BYTES        // 61_440
TrueSeal.MAX_GROUP_SIZE           // 32
// No capability negotiation (ADR-0022), so these are constants.
