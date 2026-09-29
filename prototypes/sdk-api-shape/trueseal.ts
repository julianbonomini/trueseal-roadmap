// PROTOTYPE — throwaway API sketch for trueseal-roadmap#12. Not compiled, not shipped.
// Package: @trueseal/sync. Every sketch file has the same sections in the same order.

// @section setup
import { TrueSeal, RelayAddress, TrueSealError } from "@trueseal/sync";

const relay = RelayAddress.parse("trueseal://9f3ac1…e07b@relay.example.com");
// Same address, typed form. The ports default to 7700 (receive) and 7701 (push).
const sameRelay = new RelayAddress({ host: "relay.example.com",
                                     publicKey: relayKeyHex,
                                     receivePort: 7700, pushPort: 7701 });

const trueseal = await TrueSeal.open({
  relay,                          // a RelayAddress or the string itself
  storageDir: "~/.trueseal",      // optional
  namespace: "default",           // optional
  maxPayloadBytes: undefined,     // optional: lower than 61_440 only
});
// open() returns straight away. It connects in the background; send() works at once.

// @section lifecycle
await trueseal.close();         // also: await using trueseal = await TrueSeal.open(…)
// After close(), every call rejects with TrueSealError code "CLOSED".

// @section receive
// Registering the message handler starts receiving. There is exactly one handler.
// The handler is awaited: resolving acks the message; rejecting retries it (5 tries).
const unsubscribe = trueseal.onMessage(async (message) => {
  await db.save(message.body, message.id);   // message.body: Uint8Array
  console.log(`from ${message.from.name}`);  // message.from: Member
});
unsubscribe();              // pauses receiving until a handler is registered again

// @section send
const id: MessageId = await trueseal.send(new TextEncoder().encode("hello"));
// Resolves once the message is in the durable outbox, never after delivery.
// Rejects with "PAYLOAD_TOO_LARGE" at once for bodies over the limit.

// @section status
trueseal.status;       // "notJoined" | "pendingJoin" | "member" | "leaving"
trueseal.me;           // { id, name } for this device
trueseal.members;      // Member[]: everyone else in the group
trueseal.connection;   // { state: "connecting" | "connected" | "disconnected" }
                       // | { state: "relayVersionUnsupported", min, max }

// @section admit
// On a device that's already in the group, or that starts a new one:
const token: string = trueseal.startPairing();   // show as QR / copyable text
// Join requests arrive as events (see Events):
//   { type: "joinRequest", request: { id, name } }
await trueseal.accept(request);  // single use: the window closes after it
trueseal.cancelPairing();        // closes the window; unaccepted requests vanish
// There is no reject: a request you don't accept never gets an answer.

// @section join
// On the new device:
await trueseal.join(token);      // status → "pendingJoin" (this survives restarts)
trueseal.cancelJoin();           // status → "notJoined"
// Once admitted: { type: "statusChanged", status: "member", reason: "joined" }

// @section membership
await trueseal.remove(member.id);  // any member may remove any other member
await trueseal.leave();            // status → "leaving", then "notJoined" (left)
// A removed or leaving device gets wiped and a fresh identity automatically.
// The same TrueSeal object stays usable and can pair again.

// @section destroy
// PROVISIONAL: semantics are being decided in trueseal-roadmap#10.
await trueseal.destroyGroup();     // → statusChanged, status "notJoined", reason "destroyed"

// @section events
const offEvents = trueseal.onEvent((event) => {  // any number of listeners
  switch (event.type) {
    case "statusChanged":      // event.reason: "created" | "joined"
      break;                   //   | "left" | "removed" | "destroyed"
    case "membersChanged":     // render event.members; don't diff events
      break;
    case "joinRequest":
      break;
    case "connectionChanged":
      break;
    case "admissionDropped":   // a re-applied admission hit 32
      break;
  }
});
// Events raised before the first listener is registered are buffered and replayed.

// @section issues
const offIssues = trueseal.onDeliveryIssue((issue) => {  // optional. Ignoring it is safe.
  switch (issue.type) {
    case "unreadable":                 // couldn't decrypt, verify or parse
    case "unauthorized":               // not from a current member
    case "heldForUpgrade":             // newer End-to-End Version; kept on relay
    case "handlerGaveUp":              // issue.messageId, issue.error
    case "sendFailed":                 // issue.reason: "tooLarge" | "malformed" | "expired"
    case "undeliverableAfterUpgrade":  // issue.messageIds
  }
});

// @section errors
class TrueSealError extends Error {
  readonly code:
    | "INVALID_RELAY_ADDRESS" | "INVALID_NAMESPACE" | "STORAGE" | "CLOSED"
    | "NOT_MEMBER" | "ALREADY_IN_GROUP" | "INVALID_PAIRING_TOKEN"
    | "PAIRING_CLOSED" | "GROUP_FULL" | "MEMBER_NOT_FOUND"
    | "PAYLOAD_TOO_LARGE" | "MESSAGE_HANDLER_ALREADY_SET";
  readonly max?: number;          // GROUP_FULL, PAYLOAD_TOO_LARGE
  readonly status?: GroupStatus;  // NOT_MEMBER
}
// if (e instanceof TrueSealError && e.code === "PAYLOAD_TOO_LARGE") …

// @section version
TrueSeal.info.sdkVersion;         // "0.3.0"
TrueSeal.info.transportVersion;   // 1
TrueSeal.info.endToEndVersion;    // 1
TrueSeal.MAX_PAYLOAD_BYTES;       // 61_440
TrueSeal.MAX_GROUP_SIZE;          // 32
// No capability negotiation (ADR-0022), so these are constants.
