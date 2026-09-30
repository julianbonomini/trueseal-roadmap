# Developer Preview Release Spec

Status: **draft, compiled 2026-09-30** from every closed decision on [Map: TrueSeal Developer Preview release][map] ([Task: compile the Developer Preview Release Spec][t27]). It adds no decisions of its own. Where decisions conflict, this spec links the open ticket and doesn't choose.

This document is an index. Each rule is stated once, briefly, with a link to the ADR that owns it. When this spec and an ADR disagree, the ADR wins, and this spec has a bug.

Open before the spec is final:
- [Decision: preview lifecycle and the criteria for 1.0][t28] fills in [section 7](#7-preview-lifecycle).
- [Decision: reconcile three conflicts between preview ADRs][t30] settles the items marked **(t30)** below.
- [Task: file the spec's work list as issues in the owning repos][t29] links each work-list line to its issue.

## 1. What the preview is

- **A developer preview.** It is published and installable, and it is openly allowed to break. There's no support promise, no SLA and no bounty. Every package is `0.x`.
- **Audience.** App developers who install an SDK, and self-hosters who run a single-node relay in Docker.
- **Three SDKs at parity.** Swift, Kotlin (Android) and TS (Node) share one API shape and one core build, and they release together.
- **No external audit.** Public claims are limited to what tests prove ([section 4](#4-public-claims-and-limitations)).

### What ships, and where

| Package | Channel | Name | Version line |
|---|---|---|---|
| Swift SDK | SwiftPM `binaryTarget` on GitHub Releases | `trueseal-sync-swift` | TrueSeal Release (lockstep, from 0.6.0) |
| Kotlin SDK (Android AAR) | Maven Central, GPG-signed | `dev.trueseal:trueseal-sync` | TrueSeal Release |
| TS SDK | npm, napi-rs per-platform packages, provenance | `@trueseal/sync`, `@trueseal/sync-<platform>` | TrueSeal Release |
| Core | git tags only | `trueseal-sync` | TrueSeal Release |
| Skills | Claude Code marketplace, `npx skills add`, `/.well-known/agent-skills` | `trueseal` plugin from `trueseal-skills` | TrueSeal Release (tagged every release) |
| Relay | GHCR, multi-arch, attested | `ghcr.io/julianbonomini/trueseal-relay` | independent, from 0.2.0 |
| Noise | git tags only | `trueseal-noise` | independent, from 0.2.0 |
| Docs | Cloudflare Pages site | trueseal-docs | not versioned, not gated |

Sources: [sync ADR-0030][s30], [docs ADR-0005][d5]. npm targets are macOS arm64 and x64, Linux x64 and arm64 (glibc), and Windows x64, on Node 20 or later. Everything is Apache-2.0.

## 2. Scope

**In scope:** trueseal-noise, trueseal-sync, trueseal-relay, trueseal-sync-swift, trueseal-sync-kotlin, trueseal-sync-ts, trueseal-e2e, trueseal-docs, and the new trueseal-skills repo ([docs ADR-0005][d5]).

**Out of scope** (the full list with reasons is on the [map][map]):
- the Hush example apps;
- a hosted public relay;
- multi-relay clusters, and Postgres as a supported backend;
- an external audit;
- padding and cover traffic;
- relay key rotation;
- Rust crates on crates.io;
- Kotlin on plain JVM as a published target;
- end-to-end forward secrecy and post-compromise security;
- Keychain or Keystore key storage, and database encryption;
- agent guidance inside SDK packages, an MCP server, and Context7;
- listing in Anthropic's plugin directory;
- behavioural agent evals in CI;
- network-level IP hiding.

## 3. Behaviour the preview must have

Each line is a summary. The ADR holds the state machine, the crash points and the rejected alternatives.

| Area | What the preview does | Owner |
|---|---|---|
| Protocol versions | Separate Transport and End-to-End Versions, both starting at 1 and bound into the cryptography. No negotiation, no mixed-version operation, typed rejection. Today's unversioned format is refused. | [sync ADR-0022][s22] |
| Pairing | The joiner trusts only the token's signing key. A persisted Pending Join gates the first manifest. A single-use Pairing Secret stops the relay from raising join requests. Unsolicited manifests are never accepted, and messages that arrive before a manifest exists are dropped. No SAS. | [sync ADR-0023][s23] |
| Fan-out metadata | Unchanged. The relay can infer likely co-membership, and this is documented. | [sync ADR-0024][s24] |
| Size | Single-frame messages. The Protocol Size Limit is 61,440 bytes of `Sync` body, checked in `send()`. Operators may only lower it. A size refusal is permanent and typed. | [sync ADR-0025][s25] |
| Delivery | At least once to an awaited handler, in per-sender order, within the TTL. The ack is sent after the handler finishes. The library deduplicates. Refusals are typed permanent or temporary. Pair and Manifest go through the outbox. Receiving starts when a handler is registered. One optional delivery-issue stream. | [sync ADR-0026][s26] |
| Membership | Any member may admit, remove or leave. Manifests are parent-linked and ordered by (version, hash). A Pending Membership Change is re-applied automatically. `leave()` ships. Removal wipes and rotates the identity. Groups are capped at 32. | [sync ADR-0027][s27] |
| SDK API | One `TrueSeal` shape in all three SDKs. Handlers rather than streams, one Relay Address string, and 13 shared error cases. The object outlives the group. | [sync ADR-0028][s28], [ADR-0032][s32] |
| Destroy Group | Revoke goes through the outbox. A persisted Destroying state holds until the relay has accepted every Revoke. Receivers forward the Revoke. It is honoured from any past or present member. No rotation inside the session. | [sync ADR-0029][s29] |
| Sealed Envelope | The relay reads only the End-to-End Version, the recipient key and the sealed payload. The signature, sequence and a sender timestamp move inside the ciphertext. A 60-day Replay Window means a message is never handled twice. **(t30)** for the TTL bound and timestamp timing. | [sync ADR-0031][s31] |
| Stored data | Session State and the relay store carry a Store Version and migrate forward. A Store Reset needs approval and resets automatically with `storeReset`. A newer store is refused with `storeTooNew`. **(t30)** for whether `Sync` entries are purged or re-sealed on an End-to-End bump. | [sync ADR-0032][s32], [relay ADR-0013][r13] |
| Relay operations | 25 s client heartbeat and relay deadlines. Quotas keyed per recipient. The relay never logs, stores or uses IPs, in any mode. No client metadata in logs outside dev mode. `/healthz` checks the store. Graceful shutdown. Fixed keypair setup. SQLite only. | [relay ADR-0012][r12] |
| Agent onboarding | Human Docs and Agent Docs authored separately. Agent Docs are canonical and have their own `llms.txt`. Shared Facts are generated. A paste-in Agent Snippet. READMEs are quickstarts. | [docs ADR-0003][d3] |
| Skills | Three workflow skills (Integrate, Pairing, Relay) in `trueseal-skills`, tagged with each TrueSeal Release. | [docs ADR-0005][d5] |
| Site | Variant E: brandbook tokens, a Journey-ordered Landing with the Seal Demo, a Journey sidebar, and Agent Docs as a separate tree. | [docs ADR-0004][d4], [brandbook][brand] |
| Release | A Release Conductor in trueseal-e2e builds candidates and runs the gate, then promotes the same bytes in the order noise, relay, core, SDKs, docs PR. | [e2e ADR-0002][e2] |

## 4. Public claims and limitations

The canonical source is the Threat Model page that trueseal-docs must ship ([Decision: the preview threat model and public security claims][t16]). The rules are:

- Every claim row names the tests that prove it, and CI fails if a named test doesn't exist.
- Numeric limits are tested on both sides of the boundary.
- A claim with no test may appear only as a Limitation or under "Not defended against".
- Banned from all public copy: "zero-trust", "zero-knowledge", "no communication graph", "structurally unknowable", "cryptographic guarantee" and "can't see your IP".
- Standard wording: *end-to-end encrypted; the relay can't read or forge messages; here is exactly what it does see.*
- IP wording ([relay ADR-0012][r12]): "The relay never logs, stores or uses your IP address. The server it runs on still sees the connection, as with any internet service. To hide your IP from the server too, use a VPN or Tor."

**Claims:** confidentiality, integrity and authenticity, group authenticity at join, replay (depends on **(t30)**), delivery, sender privacy toward the relay, transport, relay operation, and removal and Destroy Group. The required evidence for each is in the claims table on [the threat model ticket][t16].

**Documented limitations:**
- no end-to-end forward secrecy;
- data at rest protected only by the OS sandbox;
- what the relay sees: device keys, online times, recipients, sizes, timing, fan-out, End-to-End Version, and often which device pushed;
- availability: any holder of a public key can use up an Inbox quota, and any current or former member can trigger Destroy Group;
- membership trust: every current member is fully trusted;
- Destroy Group limits;
- no SAS, so a photographed token can be used while the window is open;
- no relay key rotation;
- handler latency is visible to the relay, and a hung handler stalls delivery.

## 5. Version scheme and wire compatibility

- **Package versions.** Core and the three SDKs form the lockstep **TrueSeal Release** from 0.6.0, and they release together even when a package is unchanged. The relay and noise are independent and restart at 0.2.0. The preview marker is `0.x` alone. Tags are `vX.Y.Z` and immutable, so a fix is a new patch version ([sync ADR-0030][s30]).
- **Protocol versions** are independent of package versions. Transport Version 1 and End-to-End Version 1. Any change to wire bytes, signing inputs or encryption inputs bumps one, even during the preview ([sync ADR-0022][s22]).
- **Compatibility.** Exactly one version of each. The relay's min equals its max.
  - An unsupported Transport Version gets a plaintext `unsupported min..max` and a close, surfaced as `relayVersionUnsupported{min,max}`.
  - A newer End-to-End Version is held unacked (up to about 100 per device).
  - An older or malformed one is acked and dropped with a local event.
  - Unknown protobuf fields never carry meaning.
- **Store versions.** Session State and the relay store start at Store Version 1 in their first preview release and migrate forward in chains ([sync ADR-0032][s32], [relay ADR-0013][r13]).
- **Reporting.** Each SDK exposes `TrueSeal.info {sdkVersion, transportVersion, endToEndVersion}`, generated from the core. The relay reports its Transport Version on `/healthz`. The docs publish a generated **Compatibility Table** covering the TrueSeal Release, relay and noise versions, both protocol versions, the Store Versions and the migration floor.

## 6. Release gates

A gated release is the lockstep TrueSeal Release, the relay or noise. Every gate below is a hard block with no override, unless it is marked *manual*. A lane that can't run counts as a failure. Docs releases aren't gated.

| ID | Gate | Evidence | Enforced by |
|---|---|---|---|
| G1 | E2E Scenario Suite passes for each SDK (Swift, Kotlin JVM test build, TS) against the Release Manifest's Candidate Artifacts | Release Evidence bundle | Release Conductor ([e2e ADR-0001][e1]) |
| G2 | Interop Smoke passes for every SDK pair, same-SDK pairs included | Release Evidence | Release Conductor |
| G3 | Adversary Client and Hostile Relay scenarios: every SDK rejects hostile input with the typed error or issue, and never acks or applies it | Release Evidence | Release Conductor |
| G4 | Android emulator smoke test of the candidate AAR (install, pair, send once) | Release Evidence | Release Conductor |
| G5 | Sync JSON test vectors are produced and verified in Rust, checked by the relay's Go tests, and checked by each SDK through its bindings | CI runs in each repo, plus Release Evidence | each repo's CI and the Conductor ([sync ADR-0022][s22]) |
| G6 | Upgrade fixtures: real stores from every release since the migration floor open and migrate, interop with un-upgraded and upgraded peers, `storeTooNew` refusal, recovery from a killed migration | Release Evidence | Release Conductor ([sync ADR-0032][s32]) |
| G7 | Relay log and store privacy: no client address in logs (normal and dev mode) or in `inbox.db`, and no client metadata in normal-mode logs | Release Evidence | Release Conductor ([relay ADR-0012][r12]) |
| G8 | Pinned inputs: every cross-repo input is pinned to an exact version and checksum, with no `releases/latest`, sibling `path` or `:latest` | Pre-promotion check | Release Conductor ([sync ADR-0030][s30], [e2e ADR-0002][e2]) |
| G9 | Pre-promotion metadata: versions match tags, Rust `rev =` SHAs, a changelog entry, Apache-2.0 metadata | Pre-promotion check | Release Conductor |
| G10 | Threat Model claims check: every claim's named tests exist | Docs CI | trueseal-docs CI ([threat model decision][t16]) |
| G11 | Reference-existence check: every name, case, limit and page referenced by Agent Docs, Human Docs and Skills exists | Docs and skills CI | trueseal-docs and trueseal-skills CI ([docs ADR-0003][d3], [ADR-0005][d5]) |
| G12 | SDK parity check: event and error cases match across the three SDKs and the core | SDK CI and the Conductor | [sync ADR-0028][s28] |
| G13 | Install-from-registry check after promotion | Release Evidence | Release Conductor |
| G14 | *Manual:* behavioural agent evals against a real relay, including nine skill cases (trigger, non-trigger and outcome for each skill), recorded as evidence | Evidence attached to the release | maintainer ([docs ADR-0003][d3], [ADR-0005][d5]) |
| G15 | *Manual, first release only:* the one-time maintainer checklist ([section 8, OPS](#ops-maintainer-only-steps)) | Checklist result | maintainer ([e2e ADR-0002][e2]) |

G1 covers the full scenario matrix in [e2e ADR-0001][e1]:
- the AGENTS.md end-to-end list, including the pairing failure and restart states;
- protocol versions;
- the relay baseline (idle timeout, refusals, the session cap, shutdown);
- Destroy Group;
- the scenario-level tests that each decision ADR names.

A red gate burns no version. A failed promotion is retried forward. A channel that rejects the bytes burns the version on every channel ([e2e ADR-0002][e2]).

## 7. Preview lifecycle

*Pending [Decision: preview lifecycle and the criteria for 1.0][t28].* It will cover notice for breaking releases, the criteria for 1.0, the end of the preview, and fixes for older 0.x releases.

## 8. Work list

Each item is filed as an issue in its owning repo by [Task: file the spec's work list][t29]. Tags:
- **fix**: a confirmed defect, which needs a failing test before the fix;
- **impl**: implement a decision;
- **test**: new test coverage;
- **docs**: documentation;
- **ci**: CI or release machinery;
- **hygiene**: cleanup;
- **approval**: needs the product owner's explicit go-ahead before it's done.

### trueseal-noise

- NOISE-1 **impl**: accept a prologue from callers so the Transport Version prefix is bound into XX and NK ([sync ADR-0022][s22]).
- NOISE-2 **fix**: concurrent send and send can reorder nonces (baseline inventory).
- NOISE-3 **test**: adversarial and timeout tests (baseline inventory).
- NOISE-4 **docs**: state the u16 frame ceiling (65,519 bytes of plaintext) as the source number for the size limit ([sync ADR-0025][s25]).
- NOISE-5 **hygiene**:
  - set the Cargo license to Apache-2.0 ([sync ADR-0030][s30]);
  - make Cargo versions match tags, from 0.2.0;
  - fix the README's claim that "XX is used between devices" ([threat model decision][t16]);
  - fix ADR-0005's claim that Go is the reference implementation.

### trueseal-sync (core and FFI)

- SYNC-1 **impl**: Transport and End-to-End Versions, version checks before DeliverAck, typed rejection, the held-blob cap, and `info` constants ([sync ADR-0022][s22]).
- SYNC-2 **impl**: produce the JSON test vectors covering:
  - signing inputs;
  - addressed encryption;
  - the Message ID;
  - every frame;
  - the version prefix;
  - one rejection per layer ([sync ADR-0022][s22], G5).
- SYNC-3 **impl**: the pairing trust anchor, Pairing Secret, Pending Join, Pairing Window and join state ([sync ADR-0023][s23]). Tests:
  - repro variants 1 to 4 pass;
  - a relay-injected `Pair`, a wrong secret and a replayed spent secret are rejected;
  - a crash at each transition.
- SYNC-4 **fix**: bind the `Pair` `signing_pub` to the Envelope signer (repro variant 5, [Task: reproduce the joiner manifest-trust hijack][t4]).
- SYNC-5 **impl**: the delivery contract ([sync ADR-0026][s26]):
  - ack after the handler;
  - 5 handler attempts, then `handlerGaveUp`;
  - serial handling;
  - typed retry classes;
  - backoff while connected;
  - 30-day `Sync` expiry;
  - control plane through the outbox;
  - receiving starts on handler registration;
  - library dedup;
  - deleting delivered rows.

  It includes the crash tests listed in the ADR.
- SYNC-6 **fix**: the connect/subscribe race (`relay.rs:148-156`, `mod.rs:457-473`).
- SYNC-7 **fix**: the manifest is restored after the reconnect loop has already started (`ffi.rs:217` vs `:274-279`).
- SYNC-8 **fix**: an oversize send is accepted and replays forever. Enforce the 61,440-byte limit in `send()` with `payloadTooLarge`, and drop oversize dev-outbox entries on load ([sync ADR-0025][s25]).
- SYNC-9 **impl**: membership convergence ([sync ADR-0027][s27]):
  - `parent` links and (version, hash) ordering;
  - Pending Membership Change;
  - `leave()` and the Leaving state;
  - wipe and rotate on removal;
  - Maximum Group Size 32.
- SYNC-10 **fix**: checked version arithmetic and a bound on version jumps (a manifest at `u64::MAX` freezes membership) ([sync ADR-0027][s27]).
- SYNC-11 **impl**: Destroy Group ([sync ADR-0029][s29]):
  - Revoke through the outbox;
  - the Destroying state;
  - forwarding;
  - honouring a Revoke from any past or present member;
  - the state table.

  It includes the unit tests listed in the ADR.
- SYNC-12 **impl**: the Sealed Envelope and Replay Window ([sync ADR-0031][s31]) with the tests in its Consequences. It depends on **(t30)** for the timestamp timing.
- SYNC-13 **impl**: Store Version, chained migrations, automatic Store Reset and `storeTooNew`, plus re-sealing outbox entries on an End-to-End bump ([sync ADR-0032][s32]). It depends on **(t30)** for `Sync` entries.
- SYNC-14 **impl**: exclude the store from cloud and device backups on every platform, and delete outbox bodies once the relay accepts them ([threat model decision][t16], [sync ADR-0032][s32]).
- SYNC-15 **impl**: reshape `ffi.rs` to the canonical API ([sync ADR-0028][s28]):
  - an async handler;
  - event and issue callbacks;
  - 13 typed errors;
  - `close()`;
  - Relay Address parsing;
  - configurable ports.
- SYNC-16 **impl**: the client sends a heartbeat every 25 s ([relay ADR-0012][r12]).
- SYNC-17 **impl**: the one connection-factory seam stays the only place sockets are opened. This keeps later IP hiding possible ([Decision: should the relay be unable to see client IPs][t26]).
- SYNC-18 **ci**:
  - drop `TRUESEAL_READ_TOKEN`;
  - make Cargo versions match tags;
  - add a candidate-build workflow and a promote workflow ([e2e ADR-0002][e2]);
  - keep one lockstep changelog with a section per SDK.
- SYNC-19 **hygiene**:
  - set the Cargo license to Apache-2.0;
  - remove `src/revocation.rs`;
  - resolve the duplicate ADR-0018;
  - fix the "Four message types" title in ADR-0009;
  - remove `progress.md`, `src/bin/NOTES.md` and `prototype_error_handling.rs`;
  - replace `.expect()` in `PersistentLog`;
  - zeroize keys (P4 TODO).
- SYNC-20 **docs**:
  - update ADR-0002's token description;
  - fix the README's overreaching claims ([threat model decision][t16]);
  - remove wording that treats member names as authentication ([sync ADR-0023][s23]).

### trueseal-relay

- RELAY-1 **fix**: DeliverAck deletes any Blob by ID without checking which inbox owns it (`router.go:67-70`, `sqlite/store.go:117`). Confirmed.
- RELAY-2 **fix**: the delivery goroutine and the heartbeat reply encrypt and write concurrently on a Receive Session (`receive.go:97,131`). Confirmed under `-race`.
- RELAY-3 **fix**: the relay doesn't check that the push routing prefix matches the Envelope's `recipient_pub` ([threat model decision][t16]).
- RELAY-4 **fix**: remove IP, key-prefix and size logging (`main.go:138,156,171`, `router.go:57`, `receive.go`). Dev mode also never logs addresses ([relay ADR-0012][r12], [IP decision][t26]).
- RELAY-5 **impl**: the Transport Version prefix, the `unsupported min..max` reply, generic `Error` codes with reason codes, and checks against the test vectors ([sync ADR-0022][s22], [ADR-0025][s25], G5).
- RELAY-6 **impl**: abuse limits and deadlines: per-inbox quotas, the per-recipient rate limit, the connection cap, the Receive Session cap per key, handshake and session deadlines, and typed refusals. Short values must be configurable for e2e ([relay ADR-0012][r12]).
- RELAY-7 **impl**: send each Blob once per Receive Session, instead of re-sending the whole inbox on every notify (`router.go:100-135`). Fix the early-blob discard (`receive.go:80-87`) ([sync ADR-0026][s26]).
- RELAY-8 **impl**:
  - refuse to start with a size limit above the protocol ceiling ([sync ADR-0025][s25]);
  - refuse to start with a TTL above the maximum, where the bound is **(t30)**.
- RELAY-9 **impl**: normal and dev logging modes (`-dev`, `TRUESEAL_RELAY_DEV=1`), with dev mode shown in `/healthz` ([relay ADR-0012][r12]).
- RELAY-10 **fix**:
  - make `/healthz` check the store and return 503 on failure (it always returns 200 today);
  - report the Transport Version there.
- RELAY-11 **fix**: graceful shutdown doesn't cancel sessions (a `context.Background()` session context). Implement the 10 s drain ([relay ADR-0012][r12]).
- RELAY-12 **fix**: `-genkey` is broken under Docker. Also:
  - auto-generate the key on first start;
  - add `trueseal-relay pubkey`;
  - add a command that prints the Relay Address ([sync ADR-0028][s28]).
- RELAY-13 **impl**: the inbox Store Version, migrations, the Operator reset flag and newer-store refusal ([relay ADR-0013][r13]).
- RELAY-14 **impl**: the Hostile Relay injection hooks, behind a Go build tag that release builds exclude ([e2e ADR-0001][e1]).
- RELAY-15 **ci**:
  - remove Dozzle, Caddy and HAProxy `tcplog` from the shipped compose file;
  - add a candidate and promote workflow with a multi-arch attested GHCR image;
  - move the VPS deploy and the `:latest` push to a manual deploy workflow that takes an exact version ([e2e ADR-0002][e2]).
- RELAY-16 **hygiene**:
  - fix the ADR-0008 drift (1 MiB, relay-initiated heartbeats, the `Error` body);
  - resolve the duplicate ADR-0010;
  - add the missing `config/relay.toml` or remove its references;
  - remove `hush-relay-result.md`;
  - fix the README's "structurally unknowable" wording ([sync ADR-0024][s24]).

### trueseal-sync-swift, trueseal-sync-kotlin, trueseal-sync-ts

Items shared by all three SDKs are filed once per SDK:
- SDK-1 **impl**: move to the canonical API ([sync ADR-0028][s28]), including `destroying` ([ADR-0029][s29]) and `storeReset` and `storeTooNew` ([ADR-0032][s32]).
- SDK-2 **test**: check the JSON test vectors through the bindings (G5).
- SDK-3 **impl**: generate `TrueSeal.info`, `maxPayloadBytes` and `maxGroupSize` from the core ([sync ADR-0030][s30]).
- SDK-4 **ci**:
  - a candidate-build and promote workflow;
  - pin core to an exact tag and checksum;
  - add the parity check (G12) ([e2e ADR-0002][e2]).
- SDK-5 **docs**: shrink the README to a quickstart marked "Developer Preview" ([docs ADR-0003][d3]).

Items specific to one SDK:
- SWIFT-1 **fix**: the relay port is silently ignored. The Relay Address fixes it.
- SWIFT-2 **ci**:
  - stop force-moving tags;
  - replace the `sed` stamp with `version`, `url` and `checksum` constants;
  - remove the stale draft release v0.0.5.
- SWIFT-3 **docs**: remove the 60-second pairing-window claim and the "Production-ready" label.
- KOTLIN-1 **fix**: the package isn't installable. Move from JitPack to Maven Central with `com.vanniktech.maven.publish`, stop committing `.so` files, and fix the POM license and url.
- KOTLIN-2 **impl**: a test-only JVM build of the same sources for the e2e headless lanes. It is never published ([e2e ADR-0001][e1]).
- KOTLIN-3 **fix**: core is pinned to `releases/latest`.
- TS-1 **fix**: the package isn't installable. Needed:
  - rename it to `@trueseal/sync`;
  - upgrade to napi v3;
  - add per-platform packages;
  - generate the loader;
  - fill `index.d.ts`;
  - replace the sibling path dependency with a pinned git tag.
- TS-2 **ci**: there is no CI. Add a build and test matrix for the npm targets.
- TS-3 **impl**: replace the untyped `TruesealSyncError` with `TrueSealError`, which has a `code` union. Remove the `HushSession` name.
- TS-4 **fix**: the high-severity advisory reported by `npm audit`.
- TS-5 **hygiene**: close the stale issues #1 to #6, and file the unmet packaging criteria as a new issue.

### trueseal-e2e

- E2E-1 **impl**: the shared Scenario Driver and the JSON control protocol, with one driver per SDK ([e2e ADR-0001][e1]).
- E2E-2 **impl**: the full scenario matrix (G1), including every e2e case the decision ADRs name. That covers pairing restarts and cancel, ordering in outbox replay, crash mid-handler, concurrent membership, Destroy Group, TTL boundaries, versions, relay limits and upgrade fixtures (G6).
- E2E-3 **fix**: the case "duplicate envelope keeps one stable application message ID" expects two deliveries. It must expect one ([sync ADR-0031][s31]).
- E2E-4 **impl**: the Interop Smoke for every SDK pair (G2).
- E2E-5 **impl**: an Adversary Client built on the Rust interop lane, plus Hostile Relay scenarios (G3).
- E2E-6 **impl**: the AAR emulator smoke test (G4).
- E2E-7 **impl**: the relay log and store privacy check (G7).
- E2E-8 **impl**: the Release Conductor ([e2e ADR-0002][e2]):
  - Release Manifests;
  - candidate staging;
  - pre-promotion checks (G8, G9);
  - ordered promotion;
  - the install check (G13);
  - Release Evidence;
  - generating the Compatibility Table;
  - one command in both modes, where "not run" counts as a failure.
- E2E-9 **ci**: stop building sibling main HEADs in gate mode. Keep Dev Mode nightly and on e2e changes.
- E2E-10 **approval**: make the repo public after a secrets check. It was decided in [e2e ADR-0002][e2], but it is outward-facing, so it gets confirmed at the time.

### trueseal-docs

- DOCS-1 **impl**: rebuild the tokens, layouts, Navbar and Landing to variant E, including the Seal Demo Island. Delete the old design-system files ([docs ADR-0004][d4]).
- DOCS-2 **impl**: restructure `nav.ts` to the Journey, and rewrite the content in the brand voice ([brandbook][brand]).
- DOCS-3 **impl**: the Agent Docs tree:
  - `llms.txt`, `llms-full.txt` and per-page Markdown;
  - the full SDK API reference;
  - the Agent Snippet as the first page;
  - generated Shared Facts;
  - `/.well-known/agent-skills/index.json` pinned to a skills tag ([docs ADR-0003][d3], [ADR-0005][d5]).
- DOCS-4 **impl**: the Threat Model page and its claims table, with the CI check (G10) ([threat model decision][t16]).
- DOCS-5 **ci**: the reference-existence check (G11).
- DOCS-6 **docs**: rewrite every overreaching claim:
  - `introduction.mdx`, `principles-and-boundaries.mdx`, `zero-trust-and-encryption.mdx`, `architecture.mdx`, `revocation.mdx` and `deploying.mdx`;
  - the 1 MiB claims in `wire-format.mdx` and `deploying.mdx`;
  - "Production-ready";
  - the Kotlin JVM claim;
  - the name "trueseal-clip" ([threat model decision][t16], [sync ADR-0024][s24], [ADR-0025][s25], [ADR-0029][s29]).
- DOCS-7 **docs**: new or rewritten pages:
  - pairing around Pending Join and the join state;
  - the delivery promise, its exceptions and the delivery-issue stream;
  - membership trust, the flicker, the 32-member limit and the automatic wipe;
  - Destroy Group wording;
  - the upgrade promise and Store Reset;
  - relay self-hosting (keypair, backup, logging modes, limits, `/healthz`, an exact image tag, the reset flag).
- DOCS-8 **docs**: the generated Compatibility Table page, a SECURITY and vulnerability-reporting page, and the preview lifecycle page (after [Decision: preview lifecycle and the criteria for 1.0][t28]).
- DOCS-9 **docs**: verify "about ten lines", "one container", the comparison cells and the other claims in brandbook section 10 before launch.
- DOCS-10 **impl**: draw the seal mascot.

### trueseal-skills (new repo)

- SKILLS-1 **impl**: create `julianbonomini/trueseal-skills` (Apache-2.0) with the `trueseal` plugin and three skills: `trueseal:integrate`, `trueseal:pairing` and `trueseal:relay` ([docs ADR-0005][d5]).
- SKILLS-2 **impl**: the Claude Code marketplace manifest and `npx skills add` support, tagged every TrueSeal Release.
- SKILLS-3 **test**: nine eval cases (G14), plus coverage by the reference-existence check (G11).

### All repos

- ALL-1 **impl**: enable GitHub private vulnerability reporting, and add `SECURITY.md` (preview, best effort, no SLA, no bounty, fixes in the next 0.x, GitHub Security Advisories) ([threat model decision][t16]).

### OPS (maintainer-only steps)

These are the one-time checklist before 0.6.0 (G15). They need the maintainer's own accounts, and several are outward-facing.
- OPS-1 **approval**: create the npm org `trueseal`, with 2FA.
- OPS-2 **approval**: create a Central Portal account, add the DNS TXT record on `trueseal.dev`, and verify `dev.trueseal`.
- OPS-3 **approval**: create a project GPG key, keep it offline, and add it as a secret on trueseal-sync-kotlin only.
- OPS-4 **approval**: do the first publish of each package, then switch npm to trusted publishing.
- OPS-5 **approval**: create the scoped GitHub App credential for the Release Conductor.
- OPS-6 **approval**: delete the GHCR image `v1.0.0` left over from the deleted relay tag. Deleting remote data needs explicit approval.

## 9. Open items

| Item | Blocks | Ticket |
|---|---|---|
| Whether `Sync` entries are purged or re-sealed on an End-to-End bump | SYNC-13, and the `undeliverableAfterUpgrade` case in SDK-1 | [Decision: reconcile three conflicts between preview ADRs][t30] |
| Relay TTL bound and sender timestamp timing | SYNC-12, RELAY-8, the replay claim | [Decision: reconcile three conflicts between preview ADRs][t30] |
| Delivery Issue cases for "sender too old", unknown frame or tag, and the Replay Window | SDK-1, SYNC-15, G12 | [Decision: reconcile three conflicts between preview ADRs][t30] |
| Preview lifecycle and 1.0 criteria | Section 7, DOCS-8 | [Decision: preview lifecycle and the criteria for 1.0][t28] |

[map]: https://github.com/julianbonomini/trueseal-roadmap/issues/1
[t4]: https://github.com/julianbonomini/trueseal-roadmap/issues/4
[t16]: https://github.com/julianbonomini/trueseal-roadmap/issues/16
[t26]: https://github.com/julianbonomini/trueseal-roadmap/issues/26
[t27]: https://github.com/julianbonomini/trueseal-roadmap/issues/27
[t28]: https://github.com/julianbonomini/trueseal-roadmap/issues/28
[t29]: https://github.com/julianbonomini/trueseal-roadmap/issues/29
[t30]: https://github.com/julianbonomini/trueseal-roadmap/issues/30
[s22]: https://github.com/julianbonomini/trueseal-sync/blob/main/docs/adr/0022-fixed-protocol-versions-no-negotiation.md
[s23]: https://github.com/julianbonomini/trueseal-sync/blob/main/docs/adr/0023-pairing-trust-anchor-and-pending-join.md
[s24]: https://github.com/julianbonomini/trueseal-sync/blob/main/docs/adr/0024-push-fan-out-linkability-accepted.md
[s25]: https://github.com/julianbonomini/trueseal-sync/blob/main/docs/adr/0025-single-frame-size-limit.md
[s26]: https://github.com/julianbonomini/trueseal-sync/blob/main/docs/adr/0026-delivery-contract.md
[s27]: https://github.com/julianbonomini/trueseal-sync/blob/main/docs/adr/0027-membership-authority-and-convergence.md
[s28]: https://github.com/julianbonomini/trueseal-sync/blob/main/docs/adr/0028-canonical-sdk-api-shape.md
[s29]: https://github.com/julianbonomini/trueseal-sync/blob/main/docs/adr/0029-destroy-group-durable-forwarded-revoke.md
[s30]: https://github.com/julianbonomini/trueseal-sync/blob/main/docs/adr/0030-distribution-channels-and-lockstep-versions.md
[s31]: https://github.com/julianbonomini/trueseal-sync/blob/main/docs/adr/0031-sealed-envelope-and-replay-window.md
[s32]: https://github.com/julianbonomini/trueseal-sync/blob/main/docs/adr/0032-versioned-session-state-and-store-reset.md
[r12]: https://github.com/julianbonomini/trueseal-relay/blob/main/docs/adr/0012-self-hosted-preview-baseline.md
[r13]: https://github.com/julianbonomini/trueseal-relay/blob/main/docs/adr/0013-versioned-inbox-store.md
[e1]: https://github.com/julianbonomini/trueseal-e2e/blob/main/docs/adr/0001-developer-preview-release-gate.md
[e2]: https://github.com/julianbonomini/trueseal-e2e/blob/main/docs/adr/0002-release-conductor-orchestration.md
[d3]: https://github.com/julianbonomini/trueseal-docs/blob/main/adr/0003-separate-agent-docs.md
[d4]: https://github.com/julianbonomini/trueseal-docs/blob/main/adr/0004-site-structure-and-visual-direction.md
[d5]: https://github.com/julianbonomini/trueseal-docs/blob/main/adr/0005-trueseal-skills.md
[brand]: https://github.com/julianbonomini/trueseal-docs/blob/main/brand/90_SYNTHESIS.md
