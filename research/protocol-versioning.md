# Research: protocol versioning patterns for layered E2EE protocols

Ticket: [trueseal-roadmap#2](https://github.com/julianbonomini/trueseal-roadmap/issues/2). Feeds #3, **Decision: wire-protocol version and compatibility policy for the preview**.

Date: 2026-09-29. Sources are primary: RFCs, protocol specs, official spec repos and reference source code. Where a spec lives in a git repo, the commit read is pinned. TrueSeal code was read at the current local `HEAD` of each repo, without modification.

## Question

How do comparable protocols put a protocol version on the wire, negotiate it or reject it explicitly, and evolve capabilities? Which pattern fits TrueSeal's layers?

For each protocol this document records:

- where the version lives;
- how downgrade is prevented;
- how mixed-version peers behave;
- how test vectors are published.

## TL;DR

- **All the protocols studied make the version cryptographically binding.** None trusts a plaintext version byte on its own.
  - WireGuard and MLS mix it into key derivation.
  - Signal MACs it.
  - Noise and libp2p-noise tie it to the handshake hash, through the protocol name and the prologue.
  - Matrix puts it in the signed, hash-addressed create event.
- **The Noise-based designs (WireGuard, libp2p-noise) refuse cipher and protocol agility.** A new version is a new identifier, and peers that don't match fail. They don't negotiate.
- **The group protocols (MLS, Matrix) fix one version per group.** It is chosen at creation from members' advertised capabilities. It changes only by creating a new group (MLS `ReInit`, Matrix tombstone), never in place.
- **Signal is the only one that runs mixed versions inside one session type.** It has a 4-bit version per message, an accepted range, and *distinct* errors for "too old" and "too new". It also refuses the downgrade case: a v4 message without the post-quantum part is rejected.
- **Extensibility and versioning are separate mechanisms.**
  - MLS and Noise recommend extensible payloads, where unknown fields and extensions are ignored.
  - MLS adds GREASE to keep "ignore unknown" working in practice.
  - Unknown values in *critical* fields (MLS proposal and credential types) still cause rejection.
- **Test vectors are published as machine-readable JSON in a public repo, separate from the prose spec.** Examples are MLS `mls-implementations/test-vectors` and Noise's cacophony-format vectors, which TrueSeal already consumes. Matrix and libp2p rely on conformance and interop suites instead.
- **TrueSeal today has no version at any layer.**
  - The Noise prologue is empty.
  - HKDF info says `v0`, but nothing else does.
  - The Ed25519 signing inputs have neither a version nor a domain label.
  - The relay and client silently drop unknown frames.
  - The client DeliverAcks a message *before* it decodes it, so a version mismatch today means silent, permanent message loss.

## 1. TrueSeal's current wire layers

What the code actually does (read-only survey):

| Layer | Who sees it | Current format | Version today | Unknown / mismatch behaviour |
|---|---|---|---|---|
| Noise transport (client ↔ relay) | client, relay | `Noise_XX_25519_ChaChaPoly_BLAKE2s` (receive) and `Noise_NK_…` (push), 2-byte BE length framing (`trueseal-noise/src/framing.rs`, `session_xx.rs:73`, `session_nk.rs:73`; relay `internal/session/receive.go:25`, `push.go:19` via `flynn/noise`) | Only the Noise protocol name. **Prologue is empty** on both sides: neither the `snow::Builder` nor the `noise.Config` sets one. | A different pattern or suite fails the handshake with a decrypt error. |
| Relay frame (inside Noise) | client, relay | `[type u8][len u32 BE][body]`. Types are 0x01 Push, 0x02 Deliver, 0x03 Heartbeat, 0x04 Ack, 0x05 Error, 0x06 DeliverAck (`trueseal-sync/src/relay.rs:43-100`; `trueseal-relay/internal/session/frame.go`). The Push body is `[recipient_pub 32][envelope]`, and the relay does not parse the envelope (`internal/relay/router.go:43`). | none | The relay does `continue` on an unknown or malformed frame (`push.go:68-70`, `receive.go:124-127`). The client ignores anything that isn't Deliver or Heartbeat (`relay.rs:298-331`). |
| Envelope protobuf (end-to-end, opaque to relay) | devices | `trueseal.sync.v0.Envelope`, with fields `sequence`, `parents`, `recipient_pub`, `signature`, `payload` (`proto/envelope.proto`) | Only in the package name `trueseal.sync.v0`, which is not on the wire. | Decode failure means a silent drop. The DeliverAck has already been sent (`relay.rs:305-307`), so the relay deletes the blob. |
| Envelope signature | devices | Ed25519 over `sequence(LE) ‖ parents ‖ recipient_pub ‖ payload` (`envelope.rs:172-185`) | none, and no domain-separation label | A new field is **not signed** unless `signing_message` changes. |
| Manifest signature | devices | Ed25519 over `group_id ‖ version(LE) ‖ members…` (`manifest.rs:54-61`). Here `version` is the *membership* version, not a protocol version. | none, and no domain-separation label | Same as the Envelope signature. |
| Addressed encryption | devices | `eph_pub(32) ‖ nonce(12) ‖ ChaCha20-Poly1305(ct)`. The key comes from HKDF-SHA256 with info `"trueseal-sync addressed encryption v0"` and no AEAD associated data (`crypto.rs:18-60`). | `v0` in the HKDF info, which is implicit | A different info string gives an AEAD failure, which can't be told apart from corruption. |
| Inner message | devices | 1-byte tag: 0x01 Pair, 0x02 Sync, 0x03 Revoke, 0x04 GroupManifest (`message.rs:18-22`) | none | `Message::decode` returns an error, and the caller drops it silently. |
| Message ID | devices, apps | `tsm1_` plus base64url(SHA-256) (`message.rs:109-115`) | `tsm1` prefix | n/a |

Two structural facts matter for the options below.

- **The Noise sessions only run between a client and the relay.** Device-to-device protection comes entirely from the Envelope signature and addressed encryption. So Noise-prologue binding can protect the *transport* version (what the relay speaks). It can't protect the *end-to-end* version, which has to be bound into the signature and HKDF/AEAD inputs.
- **The relay is store-and-forward.** A sender can't negotiate with an offline recipient in real time. A blob written today may be read after a client upgrade, up to the inbox TTL later. This is the same constraint Signal and MLS face. WireGuard, libp2p and plain Noise sessions don't have it.

## 2. Protocol survey

### 2.1 Noise Protocol Framework (rev 34)

Source: <https://noiseprotocol.org/noise.html>, spec repo `noiseprotocol/noise_spec@ecdf084`.

- **Where the version lives.**
  - The full protocol name, for example `Noise_XX_25519_ChaChaPoly_BLAKE2s`, is the first input to the handshake hash. `InitializeSymmetric(protocol_name)` sets `h` from it (§5.2), and `Initialize` then calls `MixHash(prologue)` (§5.3).
  - Noise defines no application version field. Instead, it says an application "might wish to support the transmission of some negotiation data prior to the handshake… Negotiation data could contain things like version information… a simple approach would be to send a single-byte type field prior to each Noise handshake message" (§13, *Negotiation data*).
- **How downgrade is prevented.**
  - Prologue (§6): "If both parties do not provide identical prologue data, the handshake will fail due to a decryption error… suppose Bob communicates to Alice a list of Noise protocols that he is willing to support… To ensure that a 'man-in-the-middle' did not edit Bob's list to remove options, Alice and Bob could include the list as prologue data."
  - Security considerations (§14, *Rollback*): "If parties decide on a Noise protocol based on some previous negotiation that is not included as prologue, then a rollback attack might be possible."
  - Caveat (§6): the prologue is authenticated but "they don't mix prologue data into encryption keys". It proves agreement. It isn't secret.
- **Mixed versions.**
  - Switching protocols mid-handshake needs a *compound protocol*, for example Noise Pipes with `XXfallback` (§10). The spec warns that these "introduce significant complexity" (§10.1).
  - Otherwise, a mismatch is a handshake failure. Nothing on the wire says *why* it failed.
- **Extensibility.** "Applications are recommended to use an extensible data format for the payloads of all messages (e.g. JSON, Protocol Buffers). This ensures that fields can be added in the future which are ignored by older implementations" (§13, *Extensibility*).
- **Test vectors.** The Noise wiki (`noiseprotocol/noise_wiki`) documents a community JSON vector format, "cacophony". TrueSeal already runs these vectors (`trueseal-noise/testdata/cacophony.json`, `tests/cacophony.rs`).

### 2.2 WireGuard

Sources: <https://www.wireguard.com/protocol/> and the whitepaper <https://www.wireguard.com/papers/wireguard.pdf>.

- **Where the version lives.** Nowhere as a field. The version is a constant string mixed into the handshake hash.
  - *Construction* is `"Noise_IKpsk2_25519_ChaChaPoly_BLAKE2s"`, and *Identifier* is `"WireGuard v1 zx2c4 Jason@zx2c4.com"`.
  - The hash starts as `Ci := Hash(Construction)` and then `Hi := Hash(Ci ‖ Identifier)` (whitepaper §5.4).
  - In Noise terms, Identifier works as a prologue.
  - Each message begins `type (1 byte) ‖ reserved := 0³ (3 bytes)` (§5.4). The whitepaper assigns no version meaning to the reserved bytes and only discusses their alignment benefit (§5.4.6).
- **How downgrade is prevented.** There is nothing to downgrade to: "WireGuard is cryptographically opinionated. It intentionally lacks cipher and protocol agility. If holes are found in the underlying primitives, all endpoints will be required to update" (whitepaper §1).
- **Mixed versions.** Not supported. A peer with a different Identifier derives a different chaining key, so its handshake fails MAC and AEAD checks.
- **Test vectors.** I found no official standalone vector set on wireguard.com. Conformance comes from the reference implementations. (This is absence of evidence, not a confirmed fact.)

### 2.3 libp2p: multistream-select and noise-libp2p

Sources: `multiformats/multistream-select@9a1fbe8` README; `libp2p/specs@78e75c6` files `connections/README.md`, `noise/README.md` and `connections/inlined-muxer-negotiation.md`.

- **Where the version lives.**
  - It's in path-style protocol IDs such as `/multistream/1.0.0` and `/noise`, sent as varint-length-prefixed, newline-terminated messages.
  - The dialer proposes an ID. The listener echoes it to accept or replies `na` to refuse. `ls` is optional, and implementations "MUST NOT depend on a remote node supporting ls" (multistream-select README).
  - "Including a version number in the protocol id simplifies the case where you want to concurrently support multiple versions… new versions will need to be registered separately" (connections spec, *Protocol Negotiation*).
- **How downgrade is prevented.**
  - The multistream-select spec says nothing about authentication or downgrade. Negotiating the *security* protocol happens in the clear, before any keys exist.
  - noise-libp2p avoids the issue for its own suite: "Supporting a single cipher suite allows us to avoid negotiating which concrete Noise protocol to use… Changes to the cipher suite will require a new version of noise-libp2p" (noise spec, *No Negotiation of Noise Protocols*). "Future versions… may define new protocol IDs using the `/noise` prefix, for example `/noise/2`."
- **Capability evolution.** noise-libp2p puts a protobuf `NoiseExtensions` registry, "modeled after RFC 6066… and RFC 9000", inside the encrypted handshake payload (noise spec, *Noise Extensions*). The inlined-muxer spec uses it to negotiate the stream multiplexer inside the handshake, which saves one round trip.
- **Mixed versions.** A node registers a handler per protocol ID and can serve several versions at once. An unsupported ID gets `na`, which is an explicit and cheap refusal.
- **Test vectors.** No vector files. Cross-implementation interop runs in `libp2p/test-plans` ("Interoperability tests for libp2p").

### 2.4 Signal (libsignal and PQXDH)

Sources: `signalapp/libsignal@e8cc2dd` `rust/protocol/src/protocol.rs`; the PQXDH spec <https://signal.org/docs/specifications/pqxdh/>.

- **Where the version lives.**
  - Every `SignalMessage` and `PreKeySignalMessage` starts with one byte, `(message_version << 4) | CIPHERTEXT_MESSAGE_CURRENT_VERSION` (`protocol.rs:106`). `CURRENT_VERSION = 4`, and `PRE_KYBER_VERSION = 3` (`protocol.rs:19-21`). Sender-key (group) messages have their own counter, `SENDERKEY_MESSAGE_CURRENT_VERSION = 3`.
  - PQXDH also binds the construction into the KDF. `info` is "An ASCII string identifying the application with a minimum length of 8 bytes", concatenated with the curve, hash and KEM names, for example `MyProtocol_CURVE25519_SHA-512_CRYSTALS-KYBER-1024` (PQXDH §2.1–2.2).
- **How downgrade is prevented.**
  - The version byte sits inside the MACed bytes. `compute_mac` covers `sender_identity ‖ receiver_identity ‖ serialized`, and `serialized` starts with the version byte (`protocol.rs:105-116, 214-229`).
  - For v4, a PreKey message with no Kyber prekey is rejected: `InvalidMessage("Kyber pre key must be present for this session version")` (`protocol.rs:481-489`).
  - PQXDH also puts both identity keys into the AEAD associated data (§3.3).
- **Mixed versions.** The receiver has an explicit window. `< 3` gives `LegacyCiphertextVersion`, and `> 4` gives `UnrecognizedCiphertextVersion` (`protocol.rs:268-277`). Keeping the two errors separate lets an app tell "peer is too old" from "I'm too old, upgrade".
- **Test vectors.** Unit tests live in the libsignal repo. I found no separately published cross-implementation vector suite.

### 2.5 MLS (RFC 9420)

Source: <https://www.rfc-editor.org/rfc/rfc9420> and the `mlswg/mls-implementations` repo.

- **Where the version lives.**
  - `enum { reserved(0), mls10(1), (65535) } ProtocolVersion` (§6).
  - It appears in the outer `MLSMessage` (§6), in the signed `FramedContentTBS` (§6.1), in `KeyPackage` (§10) and in `GroupContext` (§8.1).
  - Every signature and derivation label is prefixed `"MLS 1.0 "` (§5.1.2, §5.1.3, §8).
- **How downgrade is prevented.**
  - `GroupContext`, which includes `version` and `cipher_suite`, is an input to the key schedule: `ExpandWithLabel(., "joiner", GroupContext_[n], …)` and `"epoch"` (§8).
  - Each `KeyPackage` advertises capabilities. "This information allows MLS session establishment to be safe from downgrade attacks" (§10).
  - At creation: "To protect against downgrade attacks, the creator MUST use the capabilities information in these KeyPackages to verify that the chosen version and cipher suite is the best option supported by all members" (§11).
  - A received KeyPackage "MUST verify that the version field of the KeyPackage has the same value as the version field of the MLSMessage" (§10). Validation requires the KeyPackage's "cipher suite and protocol version… match those in the GroupContext" (§10.1).
- **Mixed versions.**
  - There are none inside a group, because the version is fixed per group.
  - Changing it takes `ReInit`: "reinitialize the group with different parameters, for example, to increase the version number… done by creating a completely new group and shutting down the old one". "A ReInit proposal is invalid if the version field is less than the version for the current group" (§12.1.5).
- **Capability evolution.**
  - Extensions and `required_capabilities` (§7.2, §13.4).
  - "A client processing a KeyPackage object MUST ignore all unrecognized values in the capabilities field… Otherwise, it could fail to interoperate with newer clients" (§13.4).
  - GREASE (§13.5, RFC 8701): clients SHOULD insert random reserved values so that peers which "incorrectly reject unknown code points" get caught. GREASE "MUST NOT be sent" in `proposal_type` or `credential_type`, because an unknown value there rejects the whole message.
  - Proposals with non-default types "MUST NOT be included in a commit unless the proposal type is supported by all the members" (§13.2).
- **Test vectors.** They're outside the RFC, in `mlswg/mls-implementations/test-vectors/*.json` (`crypto-basics`, `key-schedule`, `message-protection`, `messages`, `welcome`, `tree-math`, and others). They are JSON arrays with hex-encoded binary, and each harness must both *produce* and *verify* them (`test-vectors.md`).

### 2.6 Matrix room versions

Sources: <https://spec.matrix.org/latest/rooms/> and <https://spec.matrix.org/latest/server-server-api/> (spec v1.19).

- **Where the version lives.** It's in `room_version` in the content of the room's `m.room.create` event, which every server signs and hashes into the DAG. It's an opaque string: "Room versions are not intended to be parsed and should be treated as opaque identifiers" (rooms, *Room version grammar*). It versions the room *algorithms* (event format, state resolution, auth rules). The client-server and server-server APIs are versioned separately.
- **How downgrade is prevented.** The version is part of the signed root event and can't change within a room. It is fixed per room, as in MLS.
- **Mixed versions.**
  - On join, the joining server sends the versions it supports (`ver` query param on `make_join`, which "Defaults to [1]").
  - If the room's version isn't among them, the resident server returns `400 M_INCOMPATIBLE_ROOM_VERSION` with the room's `room_version`, which is explicit and machine-readable.
  - A room moves between versions only by *upgrading*: a new room, linked by `m.room.tombstone`. "Due to versions not being ordered or hierarchical… a room can 'upgrade' from version 2 to version 1."
- **Lifecycle policy.** Versions are "stable" or "unstable". They "can switch between stable and unstable periodically for a variety of reasons, including discovered security vulnerabilities and age". "Servers SHOULD use room version 12 as the default."
- **Test vectors.** None. Conformance is the `matrix-org/complement` suite ("Matrix compliance test suite").

## 3. Cross-cutting findings mapped to TrueSeal

1. **Bind the version, don't just label it.**
   - Every surveyed protocol makes a version mismatch fail cryptographically: through the handshake hash (Noise, WireGuard), a MAC (Signal), the key schedule (MLS) or a signed root (Matrix).
   - TrueSeal already has two binding points it doesn't use: the Noise prologue for the transport, and the Ed25519 signing inputs plus AEAD associated data for end-to-end.
   - The HKDF `v0` label is the only binding today, and it covers addressed encryption only.
2. **Transport and end-to-end versions are separate problems.**
   - The Noise prologue can only prove that the client and relay agree.
   - Device-to-device compatibility has to live in the Envelope, its signature and the inner message. It can't be negotiated live because recipients are offline.
   - This split matches Matrix (API versions vs room versions) and Signal (transport vs `CiphertextMessage` version).
3. **Explicit rejection beats silent drop.**
   - multistream `na`, Matrix `M_INCOMPATIBLE_ROOM_VERSION` and Signal's `Legacy…` vs `Unrecognized…` all tell the peer *why*.
   - TrueSeal silently drops unknown frames at both ends, and because the DeliverAck comes before decode, the relay deletes the undecodable blob. Any versioning scheme needs a "can't process, don't delete" or "reject with reason" path. Otherwise mixed versions lose data invisibly.
4. **Negotiation adds risk.** Noise (§13, §14) and noise-libp2p both steer away from cipher/protocol negotiation. When negotiation does happen before the handshake, Noise says to put it in the prologue.
5. **Group protocols fix the version per group and upgrade by re-creation.** Both MLS and Matrix do this. TrueSeal already has two pieces that could serve the same role:
   - a signed per-group object, the `GroupManifest`;
   - a "rebuild the group" primitive, Destroy Group.
6. **Extensibility is not versioning.**
   - Protobuf lets new fields be added and ignored, which is what Noise §13 recommends.
   - TrueSeal's hand-built signing inputs don't cover new fields, though. A security-relevant field added later would be unsigned unless the signing input also changes. Changing the signing input is itself a version change.
   - MLS's split between "ignore unknown" (extensions) and "reject unknown" (critical fields), plus GREASE, is the established way to keep that boundary honest.
7. **Test vectors are separate, machine-readable artifacts.** MLS and Noise publish JSON vectors that every implementation must produce and verify. TrueSeal has Noise vectors but no sync-level vectors (Envelope, signing input, addressed encryption, message ID). Adding a version creates a natural first vector set.

## 4. Options for TrueSeal

These are the candidate policies for #3. Each option is described per layer. Deciding among them, and on the preview support window, is left to the grilling ticket.

### Option A: One protocol epoch, bound everywhere, reject on mismatch (WireGuard and noise-libp2p style)

- **Design.**
  - Define one protocol identifier, for example `trueseal/1`.
  - Put it in the Noise prologue for both XX and NK.
  - Put it in the HKDF info and in a domain-separation prefix on the Envelope and Manifest signing inputs.
  - Optionally add a plaintext version field on the Envelope or frame, for diagnostics only.
  - There is no negotiation. A mismatch fails the handshake or the verify step.
  - The relay closes with an explicit error, and the client does not DeliverAck blobs it can't decode.
- **Pros.**
  - Smallest surface.
  - Downgrade is impossible by construction.
  - Very easy test vectors.
  - Matches Noise's advice (§13, §14) and precedent (WireGuard §1, noise-libp2p).
- **Cons.**
  - Every version bump is a flag day for all devices in a group *and* the relay.
  - Blobs in inboxes at bump time become undeliverable.
  - A handshake failure is opaque: Noise gives no reason, so a separate plaintext hint is needed for good UX.
- **Facts in favour.**
  - Pre-launch, with no production users.
  - One relay operator.
  - SDKs all wrap one Rust core, so a coordinated bump is cheap now.
  - The current Noise suite is already fixed with no agility.

### Option B: Per-layer versions with an accepted range and distinct errors (Signal style)

- **Design.**
  - **Transport:** a version in the prologue plus a first-frame hello, or a relay-advertised range. The relay accepts `[min,max]` and replies with a `VersionUnsupported{min,max}` frame.
  - **End-to-end:** a version field in the Envelope that is covered by the signature, plus version-specific HKDF info.
  - **Receiver:** has a window and reports `TooOld` or `TooNew` separately.
  - **Sender:** emits the lowest version all recipients accept. It learns what they accept from out-of-band knowledge or by being conservative.
- **Pros.**
  - Allows rolling upgrades.
  - Mixed-version groups keep working inside the window.
  - Errors are actionable.
  - Layers evolve independently, for example a relay-frame change without an E2E change.
- **Cons.**
  - Senders need to know recipients' versions, and a store-and-forward relay can't tell them. Without that knowledge, a sender either picks the minimum version (weakest common denominator) or risks stranding blobs.
  - More code paths and more test vectors per version.
  - A window invites downgrade unless the minimum is enforced and the version is signed.
- **Facts in favour.**
  - Signal solves the same offline, asynchronous problem this way (`protocol.rs:268-277`).
  - The Hush apps ship through app stores, where client versions lag.
  - The relay and SDK release cadences differ.

### Option C: Group-scoped protocol version in the signed Manifest, plus capability advertisement (MLS and Matrix style)

- **Design.**
  - Each `ManifestMember` advertises its supported protocol versions and capabilities.
  - The `GroupManifest` carries the group's protocol version. It's signed and mixed into the Envelope signing input.
  - A creator or admitter must pick the highest version every member supports, which is MLS §11's anti-downgrade rule.
  - A new member that doesn't support the group version is refused at pairing, with an explicit error like Matrix's `M_INCOMPATIBLE_ROOM_VERSION`.
  - Raising the version means rebuilding the group (MLS `ReInit`, Matrix tombstone), which could reuse Destroy Group.
  - The transport version is still handled as in A or B.
  - Unknown extension fields are ignored and GREASEd, while unknown critical fields are rejected (MLS §13.4–13.5).
- **Pros.**
  - Solves the "sender doesn't know recipients" problem in B. The manifest *is* the shared knowledge.
  - Downgrade resistance comes from signatures TrueSeal already has.
  - Well-studied precedent.
  - It's the only option that gives mixed-version *capability* evolution without a flag day.
- **Cons.**
  - Couples versioning to the membership state machine, which already has open defects: equal-version manifest forks, joiner manifest trust, and control messages not queued.
  - Needs a migration path for the manifest schema.
  - The largest scope of the three.
- **Facts in favour.**
  - TrueSeal already has a signed per-group manifest and a group-rebuild primitive.
  - Both group-oriented protocols studied chose this shape.

### Option D: Pre-handshake negotiation for the relay transport only (multistream-select style, prologue-bound)

- **Design.**
  - Before Noise starts, the client sends its supported transport versions and the relay picks one or replies `na`.
  - The transcript (offered list and choice) goes into the Noise prologue, per Noise §6, so tampering fails the handshake.
  - End-to-end versioning is handled separately by A, B or C.
- **Pros.**
  - Explicit, cheap refusal.
  - Lets one relay serve several client generations at once, which libp2p does by registering handlers per protocol ID.
  - Downgrade-safe because of the prologue binding.
- **Cons.**
  - Adds a round trip, or a compound flow, before every session. Noise calls negotiation data a source of "significant complexity and security risks such as rollback attacks" (§13).
  - Plaintext negotiation reveals the protocol version to network observers.
  - Only solves the client ↔ relay half.
- **Facts in favour.**
  - The relay is the one component that must talk to every client generation at once.
  - libp2p shows it working at scale when the negotiated list is authenticated, which noise-libp2p achieves with in-handshake extensions.

### Which facts favour which

| Fact | Favours |
|---|---|
| Pre-launch, no users, one relay operator, one Rust core behind all SDKs | A |
| Noise §13/§14 and WireGuard/noise-libp2p reject agility and negotiation | A, D only if prologue-bound |
| Store-and-forward with offline recipients, so no live E2E negotiation | B only with known recipient versions, C |
| App-store clients lag, and the relay and SDKs release on different cadences | B, C, D for the transport |
| A signed per-group manifest and a Destroy Group rebuild path already exist | C |
| Open membership state-machine defects (forks, joiner trust) | against C for now, or C after those are fixed |
| Today's silent drop plus DeliverAck-before-decode means mismatches lose data | every option needs an explicit reject / no-ack path |
| Signing inputs are hand-built with no domain label, so new fields are unsigned | every option needs a versioned, domain-separated signing input |
| MLS and Noise publish JSON vectors that each implementation must produce and verify | every option should ship sync-level vectors |

The options can be combined. For example, A for the preview, with the Envelope and signing-input version field reserved so B or C can be added later without a second flag day. Choosing such a combination is part of #3.
