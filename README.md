# TrueSeal Roadmap

Planning and release tracking that spans the TrueSeal repositories. There is no code here.

## Repositories in scope

| Repository | Role |
|---|---|
| [trueseal-noise](https://github.com/julianbonomini/trueseal-noise) | Noise XX and NK transport (Rust) |
| [trueseal-sync](https://github.com/julianbonomini/trueseal-sync) | Identity, pairing, membership, addressed encryption, outbox (Rust core + UniFFI) |
| [trueseal-relay](https://github.com/julianbonomini/trueseal-relay) | Blind ciphertext relay with durable inboxes (Go) |
| [trueseal-sync-swift](https://github.com/julianbonomini/trueseal-sync-swift) | Swift SDK |
| [trueseal-sync-kotlin](https://github.com/julianbonomini/trueseal-sync-kotlin) | Kotlin SDK |
| [trueseal-sync-ts](https://github.com/julianbonomini/trueseal-sync-ts) | TypeScript / Node SDK |
| [trueseal-e2e](https://github.com/julianbonomini/trueseal-e2e) | Cross-repo end-to-end harness |
| [trueseal-docs](https://github.com/julianbonomini/trueseal-docs) | Public docs site |

The Hush apps are example consumers. They are not in scope.

## How this repo is used

- **Maps.** A map is one issue labelled `wayfinder:map`. It states the destination and indexes the decisions made so far.
- **Tickets.** Each decision ticket is a sub-issue of its map. It carries a `wayfinder:<type>` label: `research`, `prototype`, `grilling` or `task`.
- **Blocking.** Tickets are ordered with GitHub's native "blocked by" relationships. The frontier is the set of open tickets that are unblocked and unassigned.
- **Claiming.** A session claims a ticket by assigning it before starting work.
- **Assets.** Inventories, research notes and specs live in this repo as markdown and are linked from the issues.
- **Execution.** Implementation work is filed as issues in the repository that owns the code, then linked back here.

## Documents

- [Baseline inventory, 2026-09-29](inventory/2026-09-29-baseline.md): what is implemented and tested across all eight repos.
