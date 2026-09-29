# Research: distribution channels for Swift, Kotlin, Node and Rust packages

- Ticket: julianbonomini/trueseal-roadmap#13 (feeds decision ticket #14)
- Date: 2026-09-29
- Scope: public distribution of `trueseal-sync-swift`, `trueseal-sync-kotlin`, `trueseal-sync-ts`, and the Rust crates `trueseal-noise` and `trueseal-sync`.
- Method: primary sources (registry and tool docs, Swift Evolution, the manifests of real UniFFI and napi-rs projects), a read-only look at the current TrueSeal release setup, and read-only registry lookups. Nothing was created, claimed or published.

This document lays out options. It does not pick one; that happens in #14.

---

## 1. Current state (as observed in the workspace)

### Core: `trueseal-sync/.github/workflows/release.yml`
- A `v*` tag builds five Apple static-lib slices, lipos them, generates UniFFI Swift bindings and assembles `TruesealSyncFFI.xcframework`. It uploads `trueseal-sync-swift-<tag>.zip` and a `.sha256` to the core GitHub Release.
- A second job builds Android `arm64-v8a` and `x86_64` `.so` files with 16 KB page alignment (verified with `llvm-readelf`), generates Kotlin bindings, and uploads `trueseal-sync-android-<tag>.zip`.
- Both jobs still rewrite GitHub URLs with `secrets.TRUESEAL_READ_TOKEN`, even though every repo is now public.
- `Cargo.toml` has `version = "0.1.0"` and `publish = false` (the tag is v0.5.0). It depends on `trueseal-noise` via `git = …, tag = "v0.1.4"`, and `trueseal-noise` also has `publish = false`.

### Swift: `trueseal-sync-swift`
- `Package.swift` declares `.binaryTarget(name: "TruesealSyncFFI", url: ".../trueseal-sync-swift/releases/download/v0.2.0/TruesealSyncFFI.xcframework.zip", checksum: ...)`.
- The release workflow downloads the pinned core artifact (`TRUESEAL_SYNC_TAG: v0.5.0`), re-zips the xcframework and computes the checksum. It then uses `sed` to replace `path: "TruesealSyncFFI.xcframework"` with `url:+checksum:`, **pushes to main, and force-moves the tag** (`git tag -f`, `git push --force`).
- Fragility found:
  1. `main` already contains `url:` (the stamped v0.2.0 commit), so the `sed` pattern no longer matches. The next release would silently keep pointing at the v0.2.0 binary unless someone fixes it by hand.
  2. Force-moving a tag that SwiftPM consumers may already have resolved changes the revision behind a version. SwiftPM records both the revision and the binary checksum in `Package.resolved` ([SE-0272](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0272-swiftpm-binary-dependencies.md)), so anyone who resolved in the gap gets a mismatch.
  3. There is still a draft release, v0.0.5.

### Kotlin: `trueseal-sync-kotlin`
- `jitpack.yml`:
  ```yaml
  jdk: 17
  before_install:
    - sdk install java 17.0.9-tem || true
  install:
    - ./gradlew lib:assembleRelease -PVERSION_NAME=${JITPACK_VERSION:-0.1.0}
  ```
- JitPack builds for all tags (`v0.3.0`, `v0.2.2`, `0.2.2`) report **Error** (`https://jitpack.io/api/builds/com.github.julianbonomini/trueseal-sync-kotlin`). The v0.3.0 build log shows SDKMan installing 17.0.9-tem, then Gradle 8.6 failing to resolve AGP 8.3.2 because the plugin "Doesn't say anything about its target Java version (required compatibility with Java 8)". In other words, Gradle still ran on JDK 8. Two root causes:
  1. The syntax is wrong. JitPack expects a list, `jdk:\n  - openjdk17`. JitPack "compiles projects using OpenJDK Java 8 by default" ([JitPack building](https://docs.jitpack.io/building/), [JitPack Android](https://docs.jitpack.io/android/)).
  2. The install command is wrong. JitPack's install step must "create build artifacts … and _also_ copy them to the local Maven repository `~/.m2/repository`". The default for Gradle is `./gradlew build publishToMavenLocal` ([JitPack building](https://docs.jitpack.io/building/)). `assembleRelease` publishes nothing, so fixing the JDK alone would still produce no artifact.
- Coordinates don't match: the POM uses `groupId = "dev.trueseal"`, `artifactId = "trueseal-sync-kotlin"`, while the release notes advertise JitPack's `com.github.julianbonomini:trueseal-sync-kotlin`. The POM `url` points at `github.com/buenomini/...`, which is the wrong owner.
- The release and CI workflows fetch core `releases/latest` rather than a pinned tag, so they are not reproducible. The release workflow **commits the `.so` files and generated bindings into git** and force-moves the tag so that JitPack can see them.
- `compileOptions`/`jvmTarget` are `1.8` (bytecode target, which is separate from the build JDK). The library is Android-only (AAR, JNA `aar`, `minSdk 24`).

### Node: `trueseal-sync-ts`
- `package.json`: the name is unscoped `trueseal-sync-ts` at version 0.1.0 (the tag is v0.2.0). There are four `napi.targets` (darwin arm64/x64, linux x64 gnu, win32 x64 msvc), **no `optionalDependencies`** and no `npm/` platform dirs. `@napi-rs/cli ^3` is paired with the `napi = "2"` crate; the napi-rs v3 migration guide says to "update the Rust crates and the CLI" together ([migration guide](https://napi.rs/docs/more/v2-v3-migration-guide)).
- `index.js` is hand-written. It only `require`s `./trueseal-sync-ts.<platform>.node` and throws otherwise. Despite the comment, it has no fallback to an installed platform package.
- Why the git install is broken: `Cargo.toml` uses `trueseal-sync = { path = "../trueseal-sync" }` (a sibling checkout), `dist/` and `*.node` are not committed, and there is no `.github/workflows` directory, so no CI builds binaries.
- The license is Apache-2.0, while core and noise are MIT (worth aligning before the first publish).

---

## 2. Registry name availability (read-only checks, 2026-09-29)

| Candidate | Check | Result |
|---|---|---|
| npm `@trueseal/sync`, `@trueseal/core` | `npm view` | 404, unused |
| npm `trueseal`, `trueseal-sync`, `trueseal-sync-ts` | `npm view` | 404, unused |
| npm scope/org `trueseal` | `GET registry.npmjs.org/-/org/trueseal/user` → 404 (the same call returns 200 for existing `napi-rs`, `swc` and user `julianbonomini`); search `scope:trueseal` → 0 | appears unclaimed |
| crates.io `trueseal-sync`, `trueseal-noise`, `trueseal` | `GET crates.io/api/v1/crates/<name>` | 404, unused |
| Maven Central `dev.trueseal*` | search.maven.org `g:dev.trueseal*` | 0 artifacts |
| Domain `trueseal.dev` | DNS: Cloudflare NS, serves the TrueSeal site | appears to be owned by the project, which enables DNS verification of `dev.trueseal` |
| GitHub `trueseal` | `gh api users/trueseal` | **taken** by an unrelated user account (created 2013). `io.github.trueseal` on Maven Central is therefore not available to us. `io.github.julianbonomini` is. |

Availability can change at any time. Names are first-come-first-served on npm and crates.io ([Cargo publishing](https://doc.rust-lang.org/cargo/reference/publishing.html): "crate names … are allocated on a first-come-first-serve basis").

---

## 3. Channels

### 3.1 Swift: SwiftPM with a remote `binaryTarget`

**How it works.**
- `binaryTarget(name:url:checksum:)` points at "an archive file that contains a binary artifact in its root directory" and "currently only supports artifacts for Apple platforms" ([PackageDescription](https://docs.swift.org/package-manager/PackageDescription/PackageDescription.html)).
- The checksum is `swift package compute-checksum <zip>`, recorded in `Package.resolved`. An attacker "needs to compromise both the server which provides the artifact as well as the git repository which provides the package manifest" ([SE-0272](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0272-swiftpm-binary-dependencies.md)).
- Versions are git tags on the repo that holds `Package.swift`. There is no registry account.

**How real UniFFI projects do it.**
- **matrix-org/matrix-rust-components-swift** is a dedicated release repo. `Package.swift` begins with `let checksum = "…"`, `let version = "…"`, and `let url = ".../releases/download/\(version)/MatrixSDKFFI.xcframework.zip"`. CI writes those three lines and creates a new tag; it never moves one.
- **mozilla/rust-components-swift** follows the same pattern (`let checksum/version/url`). The zip is hosted on Mozilla's Taskcluster, and a new tag is cut per nightly or release.
- **bitwarden/sdk-swift** hard-codes url+checksum per commit (Azure blob) and publishes releases named `BitwardenFFI-<ver>-<sha>.xcframework.zip`.

**Setup for TrueSeal.**
1. Keep `trueseal-sync-swift` as the SwiftPM repo.
2. Change release CI so that it: (a) downloads the **pinned** core zip and verifies its `.sha256`; (b) writes `let version/url/checksum` constants (as Matrix and Mozilla do) instead of a `sed` swap from `path:`; (c) commits, then creates the tag on that commit **once**, with no force-moves. It can either release from a release commit on main, or have CI create the tag rather than a human.
3. For local development, use a `useLocalBinary` env switch or a separate `Package@local` path rather than the "don't commit this change" comment.
4. Optionally list the package on the Swift Package Index. This is free and needs no namespace claim.

**Accounts or approvals.** None beyond the existing GitHub repo. Hosting on GitHub Releases is free for public repos.

**Reproducibility.**
- Good once the core tag is pinned and tags are immutable. The checksum in `Package.resolved` detects artifact swaps.
- Static libraries rebuilt from the same source are not guaranteed to be byte-identical, so re-running a release produces a new checksum. Build once and never re-upload under the same tag.

**CI.** A `macos-latest` runner is already in use. No secrets are needed once `TRUESEAL_READ_TOKEN` is removed.

**Cost.** Free.

**Fit.** High. This is the standard channel for UniFFI Swift and the setup already mostly exists. The work is fixing tag immutability and the stamp step, not changing channel.

### 3.2 Kotlin/Android: Maven Central vs JitPack vs GitHub Packages

#### (a) Maven Central (Sonatype Central Publisher Portal)

**Requirements** ([requirements](https://central.sonatype.org/publish/requirements/)):
- Sources and Javadoc jars ("placeholder JARs … are acceptable").
- `.md5` and `.sha1` checksums for every file.
- A GPG `.asc` signature for every file.
- POM `name`, `description`, `url`, license, developers and SCM.
- No `-SNAPSHOT` in release versions.

**Namespace** ([register namespace](https://central.sonatype.org/register/namespace/)):
- A custom domain needs a DNS TXT record with the verification key. For `dev.trueseal` the record goes on `trueseal.dev`. Verifying the domain covers every sub-group (`dev.trueseal.*`).
- Alternatively, `io.github.<user>` is granted automatically when signing up with GitHub. For us that is `io.github.julianbonomini`, because `io.github.trueseal` belongs to an unrelated GitHub user.

**Signing** ([GPG](https://central.sonatype.org/publish/requirements/gpg/)):
- The key must be published to `keyserver.ubuntu.com`, `keys.openpgp.org` or `pgp.mit.edu`.
- Default validity is two years, so the key needs renewal and re-publication.

**Tooling:**
- OSSRH "reached end of life and has been shut down" as of 2025-06-30 ([OSSRH EOL](https://central.sonatype.org/pages/ossrh-eol/)).
- Sonatype has "no official Gradle plugin" for the Portal and points to community plugins ([Portal Gradle](https://central.sonatype.org/publish/publish-portal-gradle/)).
- The common choice is `com.vanniktech.maven.publish`: `publishToMavenCentral()` plus `signAllPublications()`, with the Portal user token supplied as `ORG_GRADLE_PROJECT_mavenCentralUsername/Password` and the in-memory key as `ORG_GRADLE_PROJECT_signingInMemoryKey{,Id,Password}`. It auto-detects AGP ([vanniktech docs](https://vanniktech.github.io/gradle-maven-publish-plugin/central/)).
- Alternatives are JReleaser, or the Portal OSSRH Staging API compatibility layer.

**Real UniFFI example.** `matrix-org/matrix-rust-components-kotlin` publishes `org.matrix.rustcomponents:sdk-android` and `crypto-android` to Maven Central (verified on search.maven.org). It uses `io.github.gradle-nexus.publish-plugin` against `https://ossrh-staging-api.central.sonatype.com/`, with signing and OSSRH credentials from env or secrets.

**Accounts or approvals needed:**
- A Central Portal account.
- A namespace claim: `dev.trueseal` (a DNS TXT change on `trueseal.dev`) or `io.github.julianbonomini`.
- A long-lived project GPG key, generated, kept offline, and uploaded to keyservers.
- Portal token and signing key stored as repo secrets.

**Reproducibility.** Central releases are immutable; a version can never be re-deployed. Consumers need only `mavenCentral()`, which most Android projects already have.

**CI.** Ubuntu, JDK 17, ~4 new secrets. The `.so` files stay CI inputs and never need committing to git.

**Cost.** Free.

**Fit.** High for a security SDK. Signed, immutable artifacts under a verified namespace, with zero consumer configuration. The cost is a one-time setup and key custody.

#### (b) JitPack

**How it works** ([building](https://docs.jitpack.io/building/), [Android](https://docs.jitpack.io/android/)):
- JitPack builds from source on demand per git tag. Coordinates are `com.github.<User>:<repo>:<tag>`; custom domains are possible but thinly documented.
- It needs `jdk:\n  - openjdk17` for AGP 8+.
- The install step must publish to `~/.m2` (`publishToMavenLocal`).
- Builds "can be removed and rebuilt".

**Accounts or approvals.** None (it uses the GitHub repo). The consumer must add `maven("https://jitpack.io")`.

**Reproducibility.**
- Weak. The artifact is produced by JitPack's build, not ours, and a deleted build can be rebuilt from the same tag with a different result.
- For TrueSeal specifically, JitPack cannot run the Rust/NDK cross-compile, so native `.so` files and generated bindings must be committed to git and the tag force-moved. That is today's fragile flow.
- Artifacts are unsigned.

**CI.** Minimal, but it depends on JitPack uptime and its build image.

**Cost.** Free for public repos.

**Fit.** Low to medium. It works for a demo if the two config bugs above are fixed, but it is a poor trust story for a security SDK.

#### (c) GitHub Packages (Maven)

**How it works.** Publish with `maven-publish` to `https://maven.pkg.github.com/<owner>/<repo>` using `GITHUB_TOKEN`.

**Consumer friction.** GitHub's docs say: "You need an access token to publish, install, and delete private, internal, and public packages". Only a classic PAT is supported ([GitHub Gradle registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-gradle-registry)). So every consumer needs a GitHub PAT, **even for public packages**.

**Real example.** Bitwarden publishes `com.bitwarden:sdk-android` to `maven.pkg.github.com/bitwarden/sdk-internal` (from `crates/bitwarden-uniffi/kotlin/sdk/build.gradle`), which suits a first-party consumer, their own app.

**Accounts or approvals.** None new.

**Reproducibility.** Good: CI-built and immutable per version, though unsigned unless we add signing.

**Cost.** Free for public packages.

**Fit.** Low for a public SDK because of the PAT requirement. It is reasonable as an internal or staging channel, for example for Hush apps or E2E.

### 3.3 Node: npm with napi-rs prebuilt `optionalDependencies`

**How napi-rs does it** ([napi-rs release](https://napi.rs/docs/deep-dive/release)):
- The root package `@scope/pkg` lists per-platform packages (`@scope/pkg-darwin-arm64`, `-win32-x64-msvc`, `-linux-x64-gnu`, …) in `optionalDependencies`. Each has `os`/`cpu` (and libc) constraints, and a generated loader picks the matching one.
- The CLI flow is `napi create-npm-dirs` → per-target `napi build` in a matrix → `napi artifacts` → `napi pre-publish` (publishes the platform packages) → `npm publish` of the root package.
- The docs warn: "A multi-platform publication is not atomic", so gate on every platform artifact being present before publishing.

**Real examples** (read via `npm view`):
- `@swc/core` → `@swc/core-darwin-arm64` etc. (`os: ["darwin"]`, `cpu: ["arm64"]`), with SLSA v1 provenance attestations.
- `@napi-rs/canvas`, with provenance.
- `lightningcss` uses the unscoped `lightningcss-<platform>` pattern and has no provenance attestation.

**Naming.**
- A scope needs an npm org (or a user of the same name). "Your organization name will also be your organization scope", and the "Unlimited public packages" plan is free ([create org](https://docs.npmjs.com/creating-an-organization)).
- `@trueseal` appears free. It would hold `@trueseal/sync` plus `@trueseal/sync-<triple>` packages.
- Unscoped names (`trueseal-sync`, `trueseal-sync-darwin-arm64`, …) avoid the org, but every platform name has to be claimed individually and is squattable.

**Provenance.**
- `npm publish --provenance` requires GitHub Actions or GitLab on cloud-hosted runners, npm ≥ 9.5.0, `permissions: id-token: write`, and a public `repository` in package.json that matches the publishing repo ([provenance](https://docs.npmjs.com/generating-provenance-statements)).
- **Trusted publishing** (OIDC, no npm token in CI) needs npm CLI ≥ 11.5.1 and Node ≥ 22.14.0, and generates provenance automatically. It is configured per package on npmjs.com, so a package likely has to exist first. There is a limit of 10 trusted publishers per package, and self-hosted runners are not supported ([trusted publishers](https://docs.npmjs.com/trusted-publishers)).
- With one root package plus N platform packages, every package needs its own trusted-publisher entry.

**Setup for TrueSeal:**
1. Upgrade the `napi`/`napi-derive` crates to v3 to match CLI v3.
2. Replace the `path = "../trueseal-sync"` dependency with a git tag or crates.io version.
3. Rename to a scoped name and add the napi `npm/` dirs and `optionalDependencies`.
4. Use the generated `index.js` loader instead of the hand-written one.
5. Add a GitHub Actions matrix. Candidate targets: macOS arm64/x64 (`macos-latest` and cross-compile), Linux x64 gnu (and optionally musl and arm64), Windows x64 msvc. Electron may need linux-arm64 and win-arm64 later.
6. Publish with provenance.

**Accounts or approvals needed:**
- An npm account with 2FA.
- An npm org `trueseal` (a namespace claim).
- Either a granular automation token as a CI secret, or trusted-publisher configuration per package after the first publish.

**Reproducibility.**
- npm versions are immutable once published (unpublish is restricted).
- Provenance links each tarball to the workflow run and commit.
- The loader must pin the platform packages to the exact root version; `napi pre-publish` syncs versions.

**CI.** A 4–7 job matrix on macOS, Ubuntu and Windows. Free for public repos.

**Cost.** Free (public org plan).

**Fit.** High. This is the standard pattern for Rust-native Node modules and needs no toolchain for consumers.

### 3.4 Rust: crates.io for `trueseal-noise` and `trueseal-sync`

**Rules** ([Cargo publishing](https://doc.rust-lang.org/cargo/reference/publishing.html), [specifying dependencies](https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html)):
- "A publish is generally permanent. The version can never be overwritten, and the code cannot be deleted" (only yank).
- Metadata required: `license`, `description`, and in practice `repository`, `homepage` and `readme`.
- The `.crate` size limit is 10 MB.
- crates.io "does not allow packages to be published with dependencies on code published outside of crates.io". The fallback is `{ git = …, version = "x.y" }` / `{ path = …, version = … }`, and dev-dependencies are exempt.

**Trusted publishing.**
- Available via `rust-lang/crates-io-auth-action@v1`, which swaps the GitHub OIDC token for a short-lived token passed as `CARGO_REGISTRY_TOKEN`.
- "You'll need to publish your first release manually" ([crates.io dev update, 2025-07](https://blog.rust-lang.org/2025/07/11/crates-io-development-update-2025-07)).

**Setup for TrueSeal:**
1. Set real versions (noise is currently 0.1.0 against tag v0.1.4; sync is 0.1.0 against v0.5.0) and remove `publish = false`.
2. Publish `trueseal-noise` first.
3. Change `trueseal-sync` to depend on `trueseal-noise = "x.y"` (optionally alongside `git`/`path` for development).
4. Check `cargo publish --dry-run` and `cargo package --list`. The `build.rs` uses `prost-build`/`protox` on `.proto` files, which must be included in the package.
5. Consider whether the `uniffi-bindgen` bin and `cli` feature belong in the published crate.
6. Downstream SDK repos (ts, and optionally the Swift/Kotlin build) can then pin by crates.io version instead of a sibling path or `releases/latest`.

**Accounts or approvals needed:**
- A crates.io account (GitHub login).
- The **first manual publish of each crate name**, which permanently claims `trueseal-noise` and `trueseal-sync`.
- Then configure trusted publishing per crate.

**Reproducibility.** Excellent. Source crates are immutable and `Cargo.lock` pins the checksums.

**CI.** Ubuntu. No secrets after trusted publishing is set up.

**Cost.** Free.

**Fit.**
- It suits Rust consumers and makes cross-repo pinning cleaner.
- Publishing is permanent, and publishing crates signals API stability. Pre-1.0 semver (`0.x`) mitigates that.
- A possible alternative is to keep the crates git-only and not publish yet. Consumers would then use `git + tag` dependencies, which crates.io-published dependents cannot use.

### 3.5 UniFFI distribution guidance

UniFFI docs explicitly disclaim distribution: the tool "will not help you ship a Rust library to these platforms" ([UniFFI manual](https://mozilla.github.io/uniffi-rs/latest/)). The observed ecosystem convention (Matrix, Mozilla, Bitwarden):
- One Rust build produces the native artifacts and generated bindings.
- A **separate thin release repo or package per platform** wraps them: an xcframework zip for SwiftPM, and an AAR on Maven Central or GitHub Packages.
- Artifacts are CI inputs and are never committed to git.
- Versions are pinned to a specific core build, not "latest".

TrueSeal's split into `trueseal-sync`, `trueseal-sync-swift` and `trueseal-sync-kotlin` already matches this layout.

---

## 4. Approval items (external accounts and namespace claims)

None of these have been done.

| # | Item | Needed for | Reversible? |
|---|---|---|---|
| A1 | Create a Sonatype Central Portal account | Maven Central | yes (account) |
| A2 | Claim namespace `dev.trueseal`: add a DNS TXT record on `trueseal.dev` (Cloudflare) | Maven Central, custom groupId | namespace effectively permanent once artifacts are published |
| A2′ | *or* use the auto-granted `io.github.julianbonomini` | Maven Central, personal groupId | coordinates permanent once published |
| A3 | Generate a project GPG signing key, publish it to keyservers, store it as a CI secret, plan renewal (default 2 years) | Maven Central | key rotation possible |
| A4 | Create the npm org `trueseal` (free plan) and enable 2FA | npm scoped packages | org can be deleted; published versions are sticky |
| A5 | Create an npm automation token, or set up trusted publishers per package after the first publish | npm CI | yes |
| A6 | Create a crates.io account and do a first manual `cargo publish` of `trueseal-noise` and `trueseal-sync` | crates.io | **no**: names and versions are permanent (yank only) |
| A7 | Choose the license for the TS SDK (Apache-2.0 vs MIT elsewhere) before the first npm publish | npm | published versions keep their license |

None of these cost money.

---

## 5. Options for TrueSeal (for decision in #14)

These are presented, not chosen.

**Option 1: "Standard registries everywhere".**
- Channels: SwiftPM binaryTarget on GitHub Releases, **Maven Central** (`dev.trueseal`), **npm `@trueseal/*`** with napi-rs optionalDependencies and provenance, and **crates.io** for both crates.
- Pros: zero-config installs for consumers on every platform; signed and immutable artifacts, with provenance on npm; clean cross-repo version pinning.
- Cons: every approval item A1–A7; key custody; permanent names; the most CI work up front.

**Option 2: "Registries for app SDKs, git for Rust".**
- Channels: as in Option 1 for Swift, Kotlin (Maven Central) and npm, but the Rust crates stay git-tag dependencies.
- Pros: avoids the permanent crates.io claim and the stability signal until the protocol stabilises.
- Cons: TS and other Rust dependents must use `git + tag`. Rust users cannot depend on it from crates they publish themselves.

**Option 3: "Minimum external footprint".**
- Channels: SwiftPM (as today, fixed), **JitPack** for Kotlin (fix `jdk: - openjdk17` and `publishToMavenLocal`; keep committing the `.so` files), npm with unscoped names and no org, crates not published.
- Pros: fewest accounts and claims.
- Cons: JitPack is unsigned and rebuilds are non-reproducible; binaries are committed to git and tags force-moved; unscoped npm platform names are squattable; weakest trust story for a security SDK.

**Option 4: "GitHub-only".**
- Channels: SwiftPM, GitHub Packages for Maven and npm, crates via git.
- Pros: no new accounts at all.
- Cons: GitHub Packages requires a PAT for every consumer, even for public packages. That is unsuitable as the primary public channel, though it could serve as a staging or internal channel alongside Option 1 or 2.

**Channel-independent fixes, needed under any option:**
- Pin core versions instead of using `releases/latest`.
- Stop force-moving tags.
- Fix the Swift stamp step.
- Remove `TRUESEAL_READ_TOKEN`.
- Align package versions with tags.
- Upgrade napi to v3.
- Remove the TS sibling `path` dependency.
- Fix the Kotlin POM `url` owner.
- Decide whether Kotlin claims JVM support (today it is Android-only).
