# Research: hiding client IP addresses from the relay

Ticket: [trueseal-roadmap#25](https://github.com/julianbonomini/trueseal-roadmap/issues/25). Sources were fetched on 2026-09-29. This note lists options and does not make a recommendation.

## Question

What are the established ways to stop a message relay from learning client IP addresses, and what would each cost TrueSeal in the preview?

## What the relay sees today (verified from local code and ADRs)

- **Transport.** The relay has two raw TCP listeners, both Noise-encrypted (`trueseal-relay/README.md`):
  - `:7700` runs Noise XX, a long-lived **Receive Session**. The device authenticates with its static key.
  - `:7701` runs Noise NK, a short-lived anonymous **Push Session** for each send.
- **Where connections are opened.** Every SDK (Swift, Kotlin, and the Node napi binding in `trueseal-sync-ts`) goes through the Rust core. The core opens both connections with `std::net::TcpStream::connect` inside two closures passed as `transport_factory` and `push_factory` (`trueseal-sync/src/ffi.rs`). That gives one seam where an alternative transport could be plugged in for all SDKs. The factories currently return a concrete `TcpStream`, so the seam would have to be widened to a generic stream.
- **Policy.** ADR-0012 (trueseal-relay) says the relay never reads, stores or keys state on IPs and never logs them in normal mode. That is a promise about the relay software. The host OS, the VPS provider and any reverse proxy still see the socket peer address.
- **What IP visibility leaks, by session type:**
  - **Receive Session.** The relay can map device key → IP → approximate location, and also see online times. ADR-0031 already lists "it knows each device's key and when it is online… and can often link pushes to devices by IP or timing" as a documented limitation.
  - **Push Session.** NK hides the sender's key, but the source IP does not change. A relay host that sees the same IP on a Receive Session and on a Push Session can re-identify the "anonymous" sender. ADR-0024's fan-out linkage also lists "from the same network address" as one of its signals.
- **Push services.** TrueSeal has no APNs or FCM wake-up path in the code today (grep over the workspace found none). If one is added later, Apple and Google will see device IPs and push tokens whatever the relay transport does. Session's FAQ states this for its own "fast mode" ([getsession.org/faq](https://getsession.org/faq)).

## The non-collusion rule (applies to every option)

- RFC 9458 §6: "the Oblivious Relay Resource cannot be operated by the same entity as the Oblivious Gateway Resource" ([RFC 9458](https://www.rfc-editor.org/rfc/rfc9458.html)).
- Apple's Private Relay design uses "two separate internet relays operated by different entities" so that "no single party — including Apple — can view both the IP address of the user and their browsing activity" ([whitepaper](https://www.apple.com/privacy/docs/iCloud_Private_Relay_Overview_Dec2021.PDF)).
- Consequence for TrueSeal: a forwarding proxy run by the relay's own operator defeats nothing against that operator.
  - The proxy sees the IP, the relay sees the traffic, and one party holds both logs.
  - It only helps if the proxy is run by someone else, or if the path runs through a network (Tor, Nym, Session) where no single node sees both ends.
  - With a self-hosted relay, "the operator" is whoever runs the Docker compose. The hop has to be outside their control.

## Options

### A. Tor onion service

The relay is published as a `.onion` address and clients reach it through Tor.

- **Threat defeated.**
  - The relay host never learns client IPs. It sees only a rendezvous circuit.
  - A network observer near the client sees that Tor is in use, but not the destination.
  - Receive and Push Sessions on separate circuits can't be joined by IP. Timing and size can still join them (see ADR-0024 below).
- **Maturity (Arti).**
  - `arti-client` 0.46.0 (2026-09-02) has `onion-service-client` and `onion-service-service` features. Its docs say "the APIs for this crate are not all yet completely stable" ([docs.rs](https://docs.rs/crate/arti-client/latest)).
  - `arti` 2.6.0 enables `onion-service-client` by default; `onion-service-service` has to be opted into ([docs.rs](https://docs.rs/crate/arti/latest)).
  - The Arti docs say "proxy and onion service support are ready for use, but not all features of C Tor are available" ([arti.torproject.org](https://arti.torproject.org/core/arti/)). The capability page still calls onion services "under development", which is inconsistent with that ([capability-limitations](https://arti.torproject.org/guides/capability-limitations)).
  - Arti 1.2.0 said "we don't (yet) recommend Arti onion services for production use, or for any purpose that requires privacy". That was about hosting ([blog](https://blog.torproject.org/arti_1_2_0_released/)). I found no later post withdrawing it.
  - The relay is Go, so it would host the onion service with C tor (mature) as a sidecar rather than with Arti.
- **Mobile.**
  - *Android:* Guardian Project ships `tor-android`, an AAR with C tor 0.4.9.13 and a `TorService`, API 24+ ([GitHub](https://github.com/guardianproject/tor-android)). It also ships "Arti Mobile" for Android and iOS ([GitLab](https://gitlab.com/guardianproject/tormobile/arti-mobile)). The Tor VPN beta for Android is built on Arti ([blog](https://blog.torproject.org/tor-vpn-beta/)).
  - *iOS:* iCepa `Tor.framework` embeds Tor and has experimental Arti podspecs; "The API is _not_ stable yet" ([GitHub](https://github.com/iCepa/Tor.framework)). Network Extensions are capped at 50 MB RAM, and Tor inside one gets killed when it goes over ([Orbot FAQ](https://orbot.app/en/faqs/), [Onion Browser FAQ](https://onionbrowser.com/faqs)). In-app Tor has no such cap, but it only runs while the app is running.
  - *Background:* iOS "may choose to reclaim resources out from underneath a network socket" when an app is suspended ([TN2277](https://developer.apple.com/library/archive/technotes/tn2277/_index.html)). Background pushes give 30 s and should be limited to "two or three per hour" ([Apple](https://developer.apple.com/documentation/usernotifications/pushing-background-updates-to-your-app)). So a suspended iOS client would have to re-bootstrap Tor and reach the onion service inside that window. I found no primary figure for how long bootstrap plus onion connect takes on a phone.
  - *Briar:* the one Tor-native mobile messenger. It is Android-only and needs a wake lock "whenever the Tor process is connected" to stay reachable ([briar-devel](https://sourceforge.net/p/briar/mailman/message/35504133/)).
- **Node.** There is no first-party Tor or Arti binding for Node. The documented route is a local Arti or C tor SOCKS proxy ([Arti guides](https://arti.torproject.org/guides/)). Arti could also be linked into the Rust core behind the transport factory, which would cover Node through napi.
- **Latency.** Tor Metrics OnionPerf, time to first response header, medians of daily medians for 2026-06-01 to 2026-09-28 ([CSV](https://metrics.torproject.org/onionperf-latencies.csv?start=2026-06-01&end=2026-09-28)):
  - Onion service: about 430 ms across all vantage points, ranging from 280 ms (DE) to 680 ms (HK).
  - Public site over Tor, for comparison: about 270 ms.
  - Onion throughput is about a third of public throughput ([throughput](https://metrics.torproject.org/onionperf-throughput.csv)).
  - These are desktop measurements, and they don't include bootstrap time.
- **Noise XX/NK impact.**
  - Noise runs unchanged inside the Tor stream, because Tor carries TCP-like streams.
  - The `.onion` address authenticates the relay's onion key. The Noise static key stays the application-level relay identity, so both have to be configured, or one derived from the other.
  - The Push Session's NK anonymity only becomes real at the network layer if each Push Session uses a fresh circuit, separate from the Receive Session's circuit (Arti supports isolation).
- **ADR-0024 impact.** Fan-out pushes that share one Push Session still arrive together, with the same sizes and timing, on one circuit. Tor removes "same network address" as a signal, but not grouping by timing or size. The relay can still infer group structure.
- **Self-host burden.** The operator runs a tor daemon next to the relay, keeps the onion key (a second critical secret besides `keypair.hex`), and gives up direct-IP reachability, unless both are offered.
- **Binary size.** Arti 1.0 called size a "still-uncracked challenge" ([blog](https://blog.torproject.org/arti_100_released/)). I found no current MB figure from a primary source. It needs measuring against each SDK artifact.

### B. Third-party MASQUE / HTTP CONNECT hop (Private Relay style)

The client tunnels its TCP connection to the relay through an HTTP proxy that someone other than the relay operator runs. Optionally there are two hops (ingress and egress) run by different parties.

- **Protocols.**
  - HTTP CONNECT (RFC 9110 §9.3.6) is enough for TCP. RFC 9458 §6.1 itself points to CONNECT when a stateful connection is needed.
  - For UDP or IP there are CONNECT-UDP ([RFC 9298](https://www.rfc-editor.org/rfc/rfc9298.html)), CONNECT-IP ([RFC 9484](https://www.rfc-editor.org/rfc/rfc9484.html)) and HTTP Datagrams ([RFC 9297](https://www.rfc-editor.org/rfc/rfc9297.html)).
- **Threat defeated.**
  - With one hop, the relay host sees the proxy's IP, not the client's. The proxy operator sees the client IP and the relay's address, but can't read Noise traffic.
  - With two hops run by different parties, neither hop sees both the client IP and the destination.
  - Privacy depends entirely on the parties not colluding and on the proxy not logging.
  - A network observer near the client sees traffic going to the proxy.
- **iCloud Private Relay does not help directly.** Apple says it covers "web browsing in Safari, DNS resolution queries, and insecure http app traffic" ([Apple developer](https://developer.apple.com/support/prepare-your-network-for-icloud-private-relay/)). TrueSeal's raw Noise-over-TCP connection is not in that list.
  - Its design is the reference for this option: the Apple-run ingress sees the IP, and the egress is run by CDNs such as Akamai ([Akamai](https://www.akamai.com/blog/cloud/powering-and-protecting-online-privacy-icloud-private-relay)) and Cloudflare ([Cloudflare](https://blog.cloudflare.com/icloud-private-relay/)). I could not confirm Fastly's role from a Fastly source.
- **Apple platform support.**
  - Since iOS 17 and macOS 14, Network.framework `ProxyConfiguration` lets an app route "your entire app or just specific connections" through MASQUE, HTTP CONNECT, SOCKSv5 or OHTTP relays. Hops can be chained with `relayHops: [relay1, relay2]` ([WWDC23 "Ready, set, relay"](https://developer.apple.com/videos/play/wwdc2023/10002/)).
  - `NERelay` and `NERelayManager` are the managed, system-wide path ([NERelay](https://developer.apple.com/documentation/networkextension/nerelay)).
  - The catch: this lives in Network.framework, while the Rust core opens `std` sockets. The Swift SDK would need to hand the core a Network.framework-backed stream.
- **Android and Node.** I found no first-party MASQUE client. HTTP CONNECT over TLS is simple enough to put in the Rust core, which would cover all SDKs.
- **Latency.** Each hop adds roughly one RTT to connection setup and nothing per message after that. I found no primary benchmark.
- **Mobile.** No bootstrap and no background daemon. Background behaviour is the same as today's direct TCP.
- **Noise XX/NK impact.** None. Noise runs end to end through the tunnel. Push Sessions could use a different proxy, or a fresh proxy connection, from the Receive Session.
- **ADR-0024 impact.** The same-address signal becomes the proxy's egress address. That may be shared by many users, or it may be distinctive if few TrueSeal users share a proxy. Timing and size linkage stays.
- **Self-host burden.** Low for the relay operator, who changes nothing. The real burden is finding an independent proxy operator: a paid commercial service, or a volunteer. That is an external dependency and possibly a paid commitment, and it has to be trusted not to collude.

### C. Oblivious HTTP (RFC 9458)

- **Roles.** Client, Oblivious Relay (sees the client IP, not the content), Oblivious Gateway (decrypts with HPKE), and Target ([RFC 9458](https://www.rfc-editor.org/rfc/rfc9458.html)).
- **Threat defeated.** The gateway and target don't see client IPs; the relay doesn't see content. Both depend on the non-collusion rule.
- **Fit.**
  - It is poor for TrueSeal's session model. OHTTP "removes linkage at the transport layer, which is only useful for an application that does not carry state between requests" (§2.1). "Clients cannot carry connection-level state between requests" (§6.1). A message can't be processed until it has fully arrived (§5.1).
  - A persistent XX Receive Session and a streamed inbox don't map onto that.
  - A redesign around discrete push and poll requests could fit, with an HPKE-encapsulated push per recipient and polling for inboxes. That would replace the Noise transport for those paths and give up real-time delivery.
  - Chunked OHTTP (draft-ietf-ohai-chunked-ohttp-08, RFC Editor queue) adds incremental processing but is still request/response ([datatracker](https://datatracker.ietf.org/doc/draft-ietf-ohai-chunked-ohttp/)).
- **Mobile.** Stateless requests suit background fetch well. Polling costs battery and delays delivery.
- **ADR-0024 impact.** One OHTTP request per recipient would break the shared connection, but timing and size would still correlate at the gateway. ADR-0024 already rejected one-session-per-recipient for this reason.
- **Self-host burden.** The operator runs the gateway (or the relay becomes one) and publishes an HPKE key config. An independent OHTTP relay operator is still required.

### D. Mixnet (Nym)

- **Design.** Mixnet mode is 5 hops: entry, three mix layers, exit. It uses Sphinx packets, per-hop exponential delays and Poisson cover traffic. Latency is "acceptable for messaging… unsuitable for real-time", and current latency figures are deferred until "after the Lewes Protocol release" ([Nym docs](https://nym.com/docs/network/mixnet-mode)). There is also a 2-hop WireGuard dVPN mode.
- **Threat defeated.**
  - The relay host never sees client IPs. A Nym address "carries no IP", and the server can itself be a Nym client, with replies over SURBs ([Nym client](https://nym.com/docs/developers/what-is-a-nym-client)).
  - Cover traffic and mixing also resist a global network observer, which Tor does not.
  - It is the only listed option that addresses ADR-0024's timing linkage, which ADR-0024 says needs "a mixnet-style transport".
- **Mobile.** The Rust SDK builds for mobile via uniffi, cargo-swift and cargo-ndk ([Nym SDKs](https://nym.com/docs/developers)).
  - The client must keep an open gateway connection, and "more cover traffic provides better unobservability but uses more bandwidth" ([cover traffic](https://nym.com/docs/network/mixnet-mode/cover-traffic)). Both conflict with iOS suspension.
  - A known issue says Android mixnet bootstrap can fail with an OCSP error.
  - I could not verify the default cover-traffic rates.
- **Node.** smolmix (TCP/UDP over the mixnet) "does not run in bare Node.js or React Native", and its API may change ([smolmix](https://nym.com/docs/developers/smolmix)). The TCP proxy is deprecated.
- **Noise XX/NK impact.** The transport is message-based, not a TCP stream. Noise would need to run over Nym messages, or a stream abstraction on top of them, and the relay would become a Nym service. This is the largest transport change of all the options.
- **Self-host burden.** The operator runs a Nym client next to the relay and depends on the Nym network, including its token and incentive model, which is an external dependency.

### E. Operator-run forwarding proxy

- It defeats a network observer standing between the proxy and the relay, and it hides the relay's real IP from clients.
- It does not stop the operator learning client IPs, because the proxy operator and relay operator are the same party (RFC 9458 §6).
- It is not an option for this goal. It is listed so it can be ruled out explicitly.

## How comparable systems handle it

- **Signal.**
  - Sealed sender hides the sender from the service. Signal wrote that "additional resistance to traffic correlation via timing attacks and IP addresses are areas of ongoing development" ([blog](https://signal.org/blog/sealed-sender/)).
  - Its subpoena responses contain only the registration date and last connection date ([bigbrother](https://signal.org/bigbrother/)). That is a retention policy, the same stance as ADR-0012, not a technical inability to see IPs.
  - Signal's TLS proxy is for censorship circumvention and does not hide the IP from Signal ([blog](https://signal.org/blog/help-iran-reconnect/)).
  - I found no explicit first-party statement that Signal sees IPs. It follows from the architecture.
- **Apple iCloud Private Relay.** Two MASQUE hops run by different entities, with blind-signature access tokens and ODoH for DNS ([whitepaper](https://www.apple.com/privacy/docs/iCloud_Private_Relay_Overview_Dec2021.PDF)). It covers Safari, DNS and insecure HTTP only.
- **Session.**
  - Its onion requests pick "three random Service Nodes and build an onion-encrypted path through them". Session chose this over Lokinet because of mobile and App Store constraints ([blog](https://getsession.org/blog/onion-requests-session-new-message-routing-solution), [docs](https://docs.getsession.org/session-network/session-protocol/onion-requests-and-message-routing)).
  - Its push "fast mode" exposes the IP and push token to Apple and Google ([FAQ](https://getsession.org/faq)).
  - Lokinet itself is desktop-only; mobile is "in development" ([lokinet.org](https://lokinet.org/)).
- **Nym.** See option D.
- **Briar.** It has no server. It uses Tor onion services, Bluetooth and Wi-Fi, plus an optional Mailbox ([how it works](https://briarproject.org/how-it-works/)). It is Android-only, offers an "only while charging" setting ([manual](https://briarproject.org/manual/)), and needs a wake lock to stay reachable. An iOS feasibility study is open with no published conclusion ([issue](https://code.briarproject.org/briar/briar/-/work_items/2282)).

## Could not verify

- A current Arti binary size in MB, and the size delta for each SDK artifact. This needs a local build measurement.
- Tor bootstrap and onion-connect times on mobile, and the battery cost per hour.
- Current Nym latency figures and the default cover-traffic rates.
- Whether Arti's onion service client or hosting is now officially recommended for production.
- A first-party MASQUE client for Android, Kotlin or Node.
- Fastly's role in Private Relay.

## Options table

| Option | Threat defeated | Cost | Mobile feasibility | Self-host burden |
|---|---|---|---|---|
| A. Tor onion service | Relay host learns no client IP. A network observer sees Tor use, not the destination. Timing and size linkage (ADR-0024) remains. | Onion connect ≈430 ms median, about ⅓ the throughput, bootstrap on cold start. Arti APIs unstable. Binary size unmeasured. | Android workable (tor-android, Arti Mobile) but needs a wake lock to stay connected. iOS limited: dies on suspension, 50 MB cap in an NE. Node via SOCKS sidecar or Arti in the core. | Run a tor sidecar and keep a second key (the onion key). |
| B. Third-party CONNECT / MASQUE hop | Relay host sees the proxy IP, not the client's, if the proxy operator doesn't collude. No protection from the proxy operator itself. | About one extra RTT per connection. Needs an external proxy operator, possibly paid. | Good. No daemon. Native on iOS 17+ via Network.framework; HTTP CONNECT is easy to put in the Rust core for Android and Node. | None on the relay. The client must configure a trusted independent proxy. |
| C. Oblivious HTTP | Gateway/relay learns no client IP, if the OHTTP relay doesn't collude. | Replaces the persistent Noise sessions with request/response push and poll. Loses real-time delivery. Needs an external OHTTP relay. | Good for background fetch. Polling costs battery and latency. | Run an OHTTP gateway and publish an HPKE key config. |
| D. Nym mixnet | Relay host learns no client IP, and cover traffic resists a global observer. The only option that addresses ADR-0024 timing linkage. | Seconds-scale latency (no current official figure). Constant cover traffic and bandwidth. Message-based transport means a large Noise redesign. | Poor. Needs an always-open gateway connection and cover traffic. Android bootstrap issue. No bare-Node support. | Run a Nym client next to the relay. Depends on the Nym network and its token model. |
| E. Operator-run proxy | Nothing against the operator (RFC 9458 §6). Only hides the relay's own IP. | Low. | Good. | Low, but it gives no benefit for this goal. |
