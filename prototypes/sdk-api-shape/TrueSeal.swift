// PROTOTYPE — throwaway API sketch for trueseal-roadmap#12. Not compiled, not shipped.
// Module: TrueSealSync. Every sketch file has the same sections in the same order.

// @section setup
import TrueSealSync

let relay = try RelayAddress("trueseal://9f3ac1…e07b@relay.example.com")
// Same address, typed form. The ports default to 7700 (receive) and 7701 (push).
let sameRelay = RelayAddress(host: "relay.example.com",
                             publicKey: relayKeyHex,
                             receivePort: 7700, pushPort: 7701)

let trueseal = try await TrueSeal.open(
    relay: relay,
    storage: .applicationSupport,          // or .directory(URL)
    namespace: "default",                  // optional
    maxPayloadBytes: nil                   // optional: lower than 61_440 only
)
// open() returns straight away. It connects in the background; send() works at once.

// @section lifecycle
await trueseal.close()      // stops the connection and handlers. The outbox persists.
// After close(), every call throws TrueSealError.closed.

// @section receive
// Registering the message handler starts receiving. There is exactly one handler.
// The handler is awaited: returning acks the message; throwing retries it (5 tries).
let sub = try trueseal.onMessage { message in
    try await db.save(message.body, id: message.id)   // Message.body: Data
    print("from \(message.from.name)")                // Message.from: Member
}
sub.cancel()                // pauses receiving until a handler is registered again

// @section send
let id: MessageID = try await trueseal.send(Data("hello".utf8))
// Returns once the message is in the durable outbox, never after delivery.
// Throws .payloadTooLarge(max:) at once for bodies over the limit.

// @section status
// TrueSeal is @Observable, so SwiftUI views re-render when these change.
trueseal.status       // .notJoined | .pendingJoin | .member | .leaving
trueseal.me            // Member(id:, name:) for this device
trueseal.members       // [Member]: everyone else in the group
trueseal.connection    // .connecting | .connected | .disconnected
                       // | .relayVersionUnsupported(min:max:)

// @section admit
// On a device that's already in the group, or that starts a new one:
let token: String = try trueseal.startPairing()    // show as QR / copyable text
// Join requests arrive as events (see Events):
//   case .joinRequest(let request)  // JoinRequest(id:, name:)
try await trueseal.accept(request)  // single use: the window closes after it
trueseal.cancelPairing()            // closes the window; unaccepted requests vanish
// There is no reject: a request you don't accept never gets an answer.

// @section join
// On the new device:
try await trueseal.join(token)   // status → .pendingJoin (this survives restarts)
trueseal.cancelJoin()            // status → .notJoined
// Once admitted: .statusChanged(.member, reason: .joined)

// @section membership
try await trueseal.remove(member.id)   // any member may remove any other member
try await trueseal.leave()             // status → .leaving, then .notJoined(.left)
// A removed or leaving device gets wiped and a fresh identity automatically.
// The same TrueSeal object stays usable and can pair again.

// @section destroy
// PROVISIONAL: semantics are being decided in trueseal-roadmap#10.
try await trueseal.destroyGroup()      // → .statusChanged(.notJoined, reason: .destroyed)

// @section events
let events = trueseal.onEvent { event in       // any number of listeners
    switch event {
    case .statusChanged(let status, let reason): // reason: .created | .joined
        break                                    //   | .left | .removed | .destroyed
    case .membersChanged(let members):           // render the list; don't diff events
        break
    case .joinRequest(let request):
        break
    case .connectionChanged(let connection):
        break
    case .admissionDropped(let name, .groupFull): // a re-applied admission hit 32
        break
    }
}
// Events raised before the first listener is registered are buffered and replayed.

// @section issues
let issues = trueseal.onDeliveryIssue { issue in   // optional. Ignoring it is safe.
    switch issue {
    case .unreadable:                          // couldn't decrypt, verify or parse
        break
    case .unauthorized:                        // not from a current member
        break
    case .heldForUpgrade(let version):         // newer End-to-End Version; kept on relay
        break
    case .handlerGaveUp(let id, let error):    // your handler threw 5 times
        break
    case .sendFailed(let id, let reason):      // .tooLarge | .malformed | .expired
        break
    case .undeliverableAfterUpgrade(let ids):  // outbox sealed under an old version
        break
    }
}

// @section errors
public enum TrueSealError: Error, Equatable, Sendable {
    case invalidRelayAddress(String)
    case invalidNamespace(String)
    case storage(String)                // can't open or write Session State
    case closed
    case notMember(status: GroupStatus) // send/remove/leave/startPairing in the wrong state
    case alreadyInGroup                 // join() while a manifest exists
    case invalidPairingToken            // includes tokens from another protocol version
    case pairingClosed                  // accept() after the window closed
    case groupFull(max: Int)            // 32
    case memberNotFound
    case payloadTooLarge(max: Int)
    case messageHandlerAlreadySet
}

// @section version
TrueSeal.info.sdkVersion          // "0.3.0"
TrueSeal.info.transportVersion    // 1
TrueSeal.info.endToEndVersion     // 1
TrueSeal.maxPayloadBytes          // 61_440
TrueSeal.maxGroupSize             // 32
// No capability negotiation (ADR-0022), so these are constants.
