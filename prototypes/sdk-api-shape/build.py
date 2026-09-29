# PROTOTYPE — renders the three API sketches side by side. Run: python3 build.py
import html, re, pathlib

HERE = pathlib.Path(__file__).parent
LANGS = [("Swift", "TrueSeal.swift"), ("Kotlin", "TrueSeal.kt"), ("TypeScript", "trueseal.ts")]

SECTIONS = [
    ("setup", "Setup and relay address",
     "Today: Swift takes a <code>URL</code> and silently drops its port, while Kotlin and TS take a bare host. The key is raw bytes, and the core hardcodes ports 7700 and 7701.",
     "One <code>RelayAddress</code> everywhere, parsed from one pasteable string that <code>trueseal-relay address</code> would print: <code>trueseal://&lt;key hex&gt;@host[:receivePort][?push=port]</code>. There's also a typed form. <code>open()</code> is async in all three SDKs."),
    ("lifecycle", "Lifecycle",
     "Today: Swift has no teardown, TS <code>dispose()</code> only removes listeners, and Kotlin <code>close()</code> tears down the session.",
     "<code>close()</code> in all three. The outbox and Session State persist; the next <code>open()</code> resumes."),
    ("receive", "Receiving messages",
     "Today: streams and EventEmitters fire and forget, and the relay ack goes out before the app has seen the message.",
     "One awaited handler (ADR-0026). Registering it starts receiving, and returning from it acks the message. <code>message.from</code> is a <code>Member</code>, so it matches <code>members</code>. Today TS's sender id doesn't."),
    ("send", "Sending",
     "Today: <code>publish</code> (Swift and Kotlin; Kotlin's is synchronous) versus <code>send</code> (TS). None of them return anything.",
     "<code>send</code> everywhere. It returns the <code>MessageId</code>, so a later <code>sendFailed</code> can be matched to it. The <code>publish(text:)</code> helpers are dropped."),
    ("status", "Status, identity and connection",
     "Today: <code>localNodeId</code> and <code>localDeviceName</code>, a boolean connection state, and no join state.",
     "New join status (ADR-0023, ADR-0027). <code>me</code> replaces the two local fields. The connection can report <code>relayVersionUnsupported</code> (ADR-0022). Each SDK exposes state the way its UI framework expects: Swift <code>@Observable</code>, Kotlin <code>StateFlow</code>, TS getters plus events."),
    ("admit", "Pairing: admitting a device",
     "Today: <code>generatePairingToken</code> or <code>pairingToken</code>. <code>acceptPairingRequest</code> returns a Bool that Swift and Kotlin throw away.",
     "<code>startPairing()</code> and <code>accept(request)</code>. <code>accept</code> throws <code>pairingClosed</code> or <code>groupFull</code> instead of returning false. There is no reject, because the protocol sends no decline (ADR-0023)."),
    ("join", "Pairing: joining",
     "Today: <code>joinGroup(token)</code>, with no way to cancel and no pending state.",
     "<code>join(token)</code> and <code>cancelJoin()</code>. The Pending Join is visible in <code>status</code> and survives restarts."),
    ("membership", "Members, remove and leave",
     "Today: <code>removeMember</code> takes a member object in Swift and Kotlin but an id string in TS. There is no leave, and wiping after removal is left to the app.",
     "<code>remove(memberId)</code> and <code>leave()</code> everywhere. On removal or leave the library wipes the device and gives it a fresh identity (ADR-0027). The same object stays usable."),
    ("destroy", "Destroy Group",
     "Today: <code>destroyGroup()</code> wipes the device and leaves the session unusable.",
     "<strong>Provisional.</strong> The name stays. What happens afterwards depends on the Destroy Group decision (trueseal-roadmap#10). The sketch assumes it behaves like removal: back to <code>notJoined</code> with a fresh identity."),
    ("events", "Events",
     "Today: Swift has 4 <code>AsyncStream</code>s, Kotlin 4 <code>Flow</code>s, and TS 7 string-named events.",
     "One event type, handled with an exhaustive <code>switch</code> or <code>when</code>. Member changes arrive as the whole list, since ADR-0027 says to render the list and not trust individual joined and left events."),
    ("issues", "Delivery issues",
     "Today: nothing. Failures are silent.",
     "One optional stream with the same six cases in every SDK (ADR-0026). Each case carries a Message ID when one exists."),
    ("errors", "Errors",
     "Today: Swift has a typed enum and Kotlin a sealed class (8 cases each), while TS has a single untyped error that holds only a message.",
     "The same 12 cases in all three SDKs. In TS that is one error class with a <code>code</code> string union and typed extras."),
    ("version", "Version and limits",
     "Today: nothing is public. TS has a hidden native <code>version()</code>.",
     "Static info with the SDK version, the Transport and End-to-End Versions, and the two protocol limits."),
]

REACT = [
    ("Entry type is <code>TrueSeal</code>", "It replaces <code>TruesealSyncClient</code>, and the brand is written <em>TrueSeal</em> everywhere. Package names belong to the distribution decision."),
    ("One relay address string", "It holds the key, the host and both ports, and the relay CLI prints it. This fixes the Swift port bug by construction."),
    ("Handlers, not streams", "<code>onMessage</code>, <code>onEvent</code> and <code>onDeliveryIssue</code> are the same in every SDK. Only state uses platform-native observation."),
    ("No reject", "An unaccepted join request just expires when the window closes."),
    ("The object outlives the group", "After removal, leave or destroy, the same <code>TrueSeal</code> object is back to <code>notJoined</code> with a fresh identity and can pair again."),
    ("<code>members</code> excludes you", "<code>me</code> is separate, as today."),
]

def highlight(code):
    out = []
    for line in code.splitlines():
        esc = html.escape(line)
        m = re.search(r"(?<!:)//.*$", esc)
        if m:
            esc = esc[:m.start()] + '<span class="c">' + esc[m.start():] + "</span>"
        out.append(esc)
    return "\n".join(out)

def split(path):
    parts, cur = {}, None
    for line in (HERE / path).read_text().splitlines():
        m = re.match(r"\s*// @section (\w+)", line)
        if m:
            cur = m.group(1); parts[cur] = []; continue
        if cur: parts[cur].append(line)
    return {k: "\n".join(v).strip("\n") for k, v in parts.items()}

code = {lang: split(f) for lang, f in LANGS}

rows = []
for key, title, today, proposed in SECTIONS:
    cols = "".join(
        f'<figure class="col"><figcaption>{lang}</figcaption><pre><code>{highlight(code[lang].get(key, "// missing"))}</code></pre></figure>'
        for lang, _ in LANGS)
    prov = ' provisional' if key == 'destroy' else ''
    rows.append(f'''<section class="area{prov}" id="{key}">
  <header><h2>{title}</h2>
    <div class="notes"><p class="today">{today}</p><p class="prop">{proposed}</p></div></header>
  <div class="grid">{cols}</div></section>''')

react = "".join(f"<li><strong>{a}</strong><span>{b}</span></li>" for a, b in REACT)
nav = "".join(f'<a href="#{k}">{t}</a>' for k, t, *_ in SECTIONS)

page = (HERE / "template.html").read_text().replace("{{REACT}}", react).replace("{{NAV}}", nav).replace("{{ROWS}}", "\n".join(rows))
(HERE / "index.html").write_text(page)
print("wrote", HERE / "index.html")
