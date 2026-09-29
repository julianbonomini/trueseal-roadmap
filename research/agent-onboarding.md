# Research: agent-ready onboarding for SDKs

Ticket: julianbonomini/trueseal-roadmap#18. Feeds decision ticket #19 (agent onboarding design).
Researched: 2026-09-29. Sources are primary (spec owners, vendor docs, vendor repos) and are linked inline. Vendor pages change often; re-verify install commands before copying them.

## Question

How do developer tools make integration "a few prompts away" for AI coding agents today, and what could TrueSeal ship?

## TL;DR

- Well-regarded dev tools now ship a **stack** of artifacts, not one: (1) a docs index for agents (`llms.txt` plus Markdown copies of every page), (2) always-on project instructions (`AGENTS.md`/`CLAUDE.md`), (3) on-demand **Agent Skills** (`SKILL.md` folders), often bundled as a **plugin** with (4) an **MCP server**, plus (5) a one-command setup CLI.
- The formats are converging on open, cross-tool standards: `AGENTS.md` (Linux Foundation / Agentic AI Foundation), Agent Skills (agentskills.io, originated at Anthropic), MCP. Tool-specific wrappers (Claude Code plugins, Cursor plugins, Codex plugins) mostly just package those.
- The strongest published evidence (Vercel/Next.js evals) says **always-present context beats on-demand retrieval for "how does this API work" knowledge**; skills win for multi-step *workflows*. In Vercel's eval, a compressed docs index in `AGENTS.md` scored 100% vs 53–79% for skills, and the skill was never invoked in 56% of runs.
- The hard problem is **staying in sync with API changes**. The patterns that work: generate agent artifacts from the same source as the docs; ship guidance **inside the versioned package** (Next.js, TanStack Intent); run **evals** in CI (Convex, Next.js, `claude plugin eval`); flag staleness when referenced sources change (TanStack Intent `intent stale`).
- For TrueSeal, the Astro docs site can emit `llms.txt`, `llms-full.txt`, and per-page `.md` files with a few static endpoints, no framework change. The bigger gap: SDK API reference lives only in each SDK repo's README, so agent docs built from the site alone would miss the API surface.

## 1. The artifact types

### 1.1 `llms.txt` / `llms-full.txt` / per-page Markdown

- **Spec:** [llmstxt.org](https://llmstxt.org/), proposed by Jeremy Howard (Answer.AI), published 2024-09-03. It is "a proposal to standardise", not a formal standard.
- **Format:** a Markdown file at `/llms.txt` (or a subpath like `/docs/llms.txt`, which covers URLs under that path). Only an H1 with the project name is required. After that come an optional blockquote summary, optional prose, and optional H2 "file lists" of `[name](url): notes` links. An `## Optional` section marks links an agent can skip when short on context.
- **Page Markdown:** the proposal asks sites to serve clean Markdown at the page URL with `.md` appended, and suggests `rel="alternate" type="text/markdown"` links for discovery.
- **`llms-full.txt`** is **not in the proposal**. It is a widespread vendor convention: the full docs concatenated into one file. Vercel ([agent resources](https://vercel.com/docs/agent-resources)), Next.js, Supabase, Prisma, and Cloudflare (per product, e.g. `developers.cloudflare.com/workers/llms-full.txt`) publish it. All of these URLs returned HTTP 200 on 2026-09-29.
- **Observed practice:**
  - Stripe: append `.md` to any docs URL ([docs.stripe.com/building-with-llms](https://docs.stripe.com/building-with-llms)).
  - Vercel and Next.js: `.md` suffix **and** `Accept: text/markdown` content negotiation, plus extra indexes (`sitemap.md`, `graph.json`, `taxonomy.json`).
  - Cloudflare: a root `llms.txt` that links one `llms.txt` per product.
  - Anthropic's Claude Code docs: a "Documentation Index" banner at the top of every Markdown page that points to `llms.txt`.
- **Use by agents:** there is no auto-discovery. An agent reads it when a user pastes the URL, when a rule or skill points to it, or when a docs MCP server or index (Context7) ingests it. Its value is as the *source* that other artifacts are built from and point at.

### 1.2 `AGENTS.md` and `CLAUDE.md` (always-on instructions)

- **Spec:** [agents.md](https://agents.md/) is plain Markdown with no required fields ("a README for agents"). In a monorepo, "the closest one takes precedence." It is now stewarded by the Agentic AI Foundation under the Linux Foundation and supported by Codex, Jules, Cursor, VS Code/Copilot, Devin, Aider, Zed, Warp and others.
- **Claude Code** ([memory docs](https://code.claude.com/docs/en/memory)):
  - Reads `CLAUDE.md` natively. Since v2.1.277 it also reads `AGENTS.md` directly, but by default **only when no `CLAUDE.md`/`CLAUDE.local.md` is on the path**.
  - The portable pattern for sharing one file across tools is a `CLAUDE.md` containing `@AGENTS.md`.
  - The docs recommend keeping each file under 200 lines and moving procedures into skills or path-scoped `.claude/rules/`.
- **Cursor** ([rules docs](https://cursor.com/docs/context/rules)):
  - Supports `.cursor/rules/*.mdc`, with frontmatter `description`, `globs`, `alwaysApply`. Rule types are Always, Intelligent, File-glob, and Manual.
  - A root `AGENTS.md` and nested `AGENTS.md` files work too.
  - Legacy `.cursorrules` is superseded.
  - Remote rules are not importable directly. They have to be packaged in a Cursor plugin (`.cursor-plugin/marketplace.json`).
- **Why it matters for a vendor:** `AGENTS.md` belongs to the *consumer's* repo, not the vendor's. Vendors therefore get guidance into it by **writing a managed block into the user's `AGENTS.md`**:
  - **Next.js** ([AI agents guide](https://nextjs.org/docs/app/guides/ai-agents)): `create-next-app` and `next dev` (16.3+) upsert a `<!-- BEGIN:nextjs-agent-rules -->` block. The block tells agents to read version-matched docs bundled at `node_modules/next/dist/docs/`. The generator also writes a `CLAUDE.md` containing `@AGENTS.md`.
  - **Convex** ([docs.convex.dev/ai](https://docs.convex.dev/ai)): `npx convex ai-files install|update|status` manages `convex/_generated/ai/guidelines.md` plus managed sections in `AGENTS.md` and `CLAUDE.md`.
  - **Supabase** ([AI prompts](https://supabase.com/docs/guides/getting-started/ai-prompts)): publishes copy-paste prompt files for Cursor, Copilot, JetBrains, Gemini and others.

### 1.3 Agent Skills and plugins (on-demand workflows)

- **Spec:** [agentskills.io](https://agentskills.io/). Originally developed by Anthropic and released as an open standard; adopted by Claude Code, Codex, Cursor, Copilot/VS Code, Gemini CLI, OpenCode, Goose and many others.
  - A skill is a folder with `SKILL.md` (frontmatter `name`, `description`, plus optional `license`, `compatibility`, `metadata`, `allowed-tools`) and optional `scripts/`, `references/`, `assets/`.
  - Skills load by **progressive disclosure**: agents keep only name and description at startup, read `SKILL.md` on activation, and open referenced files as needed.
- **Anthropic authoring guidance** ([best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)):
  - `name` ≤ 64 chars, lowercase with hyphens. `description` ≤ 1,024 chars, third person, says what the skill does and when to use it.
  - Keep the body under 500 lines, with references one level deep.
  - "Build evaluations first" (at least three scenarios, against a baseline without the skill) and test on every model you target.
- **Claude Code** ([skills](https://code.claude.com/docs/en/skills)):
  - Personal skills live in `~/.claude/skills/`, project skills in `.claude/skills/`, plugin skills in `<plugin>/skills/`.
  - The combined `description` + `when_to_use` text is truncated at 1,536 chars in the listing.
  - Plugin skills are namespaced as `/plugin:skill`.
- **Plugins** ([overview](https://code.claude.com/docs/en/plugins)): a directory with `.claude-plugin/plugin.json` that bundles skills, subagents, hooks, and MCP servers as one installable, versioned unit.
- **Marketplaces** ([create a marketplace](https://code.claude.com/docs/en/plugin-marketplaces)):
  - A marketplace is a git repo with `.claude-plugin/marketplace.json` (`name`, `owner`, `plugins[]`). Plugin sources can be a relative path, `github`, `git-subdir`, `url`, `archive`, `npm`, or `command`.
  - Users run `claude plugin marketplace add owner/repo`, then `claude plugin install name@marketplace`.
  - A repo can require it through `.claude/settings.json` (project scope).
  - Anthropic also runs an official directory (`claude-plugins-official`), for example `claude plugin install stripe@claude-plugins-official`.
  - Enabled plugins cost context every turn, because each skill's name and description is listed.
- **Cross-agent installer:** Vercel's [`skills` CLI](https://github.com/vercel-labs/skills) (`npx skills add owner/repo`) installs Agent Skills into 75+ agents' skill directories; [skills.sh](https://skills.sh) is its directory and leaderboard. Manually installed skills do not auto-update: users run `npx skills update`.
- **Web discovery:** [Cloudflare's Agent Skills Discovery RFC](https://github.com/cloudflare/agent-skills-discovery-rfc) (draft v0.2.0) defines `/.well-known/agent-skills/index.json` entries with `name`, `type` (`skill-md`|`archive`), `description`, `url`, and a `sha256` digest. Supabase publishes one (`supabase.com/.well-known/agent-skills/index.json`, schema `schemas.agentskills.io/discovery/0.2.0`). Stripe publishes a similar index at `docs.stripe.com/.well-known/skills/index.json`, and `npx skills add https://docs.stripe.com` consumes it.

### 1.4 MCP servers

- **Spec:** [modelcontextprotocol.io](https://modelcontextprotocol.io/docs/getting-started/intro). MCP is an open protocol that lets agents call tools, read resources, and use prompts, over stdio (local) or Streamable HTTP (remote). Claude, ChatGPT, VS Code, Cursor and others support it.
- **Vendor pattern:** a **remote, authenticated server** that combines doc search with actions against the user's live account:
  - Stripe: `mcp.stripe.com`
  - Vercel: `mcp.vercel.com`
  - Prisma: `mcp.prisma.io/mcp`
  - Clerk: `clerk mcp install`
  - Next.js adds a local dev-server MCP at `/_next/mcp` for runtime state (routes, compile errors).
- **Docs-only MCP** is mostly outsourced to indexes like Context7 (below). For an SDK with no hosted account state, MCP adds little over docs plus skills unless there is something live to query.

### 1.5 Hosted doc indexes (Context7)

- [Context7](https://github.com/upstash/context7) (Upstash) is a remote MCP server (`https://mcp.context7.com/mcp`, API key) with tools `resolve-library-id` and `query-docs`. `npx ctx7 setup --claude|--cursor|--opencode` installs it.
- **Library owners** ([adding libraries](https://context7.com/docs/adding-libraries)) submit a GitHub repo at context7.com/add-library, can commit `context7.json` to control which folders are indexed, and can claim the library for an admin panel.
- Refresh runs automatically "based on popularity", or on every push to the default branch through the Context7 GitHub Action.
- Cost to the vendor is low: the vendor does not control ranking or presentation, but gets coverage in agents that already have Context7 installed.

## 2. What well-regarded tools ship (as of 2026-09-29)

| Vendor | Docs for agents | Always-on / rules | Skills | Plugin | MCP | One-command setup | Sync / quality mechanism |
|---|---|---|---|---|---|---|---|
| **Stripe** ([1](https://docs.stripe.com/building-with-llms), [2](https://docs.stripe.com/skills.md), [3](https://docs.stripe.com/agents/plugin.md)) | `llms.txt`, `.md` on every URL, `stripe docs` CLI | — | Yes, served from docs site `/.well-known/skills/` | Claude Code (official directory), Codex, Cursor, Grok. Bundles MCP + skills and **auto-updates** | Remote `mcp.stripe.com` | `stripe agent setup` detects installed agents | Skills are served from the docs site; the plugin auto-updates |
| **Vercel / Next.js** ([1](https://vercel.com/docs/agent-resources), [2](https://nextjs.org/docs/app/guides/ai-agents)) | `llms.txt`, `llms-full.txt`, `.md` + `Accept: text/markdown`, `sitemap.md`, `graph.json` | Managed block in `AGENTS.md` + `CLAUDE.md` → **docs bundled in the npm package** | `vercel/next.js/skills` (in the framework repo) | `npx plugins add vercel/vercel-plugin` | `mcp.vercel.com`; local `/_next/mcp` | `create-next-app`; `next dev` auto-writes agent files | Version-matched docs ship with the package; public evals at nextjs.org/evals |
| **Supabase** ([1](https://supabase.com/docs/guides/getting-started/ai-prompts), [2](https://github.com/supabase/agent-skills)) | `llms.txt` → `.md` pages, `llms-full.txt` | Copy-paste prompt files per IDE | `supabase/agent-skills` | Repo is also a Claude Code marketplace | Yes (Supabase MCP) | `npx skills add supabase/agent-skills` | Release Please releases; auto-deployed `.well-known/agent-skills` |
| **Clerk** ([1](https://clerk.com/docs/guides/ai/overview)) | `clerk.com/docs/llms.txt` | Prompts inside quickstarts | `clerk/skills` | — | `clerk mcp install` | `npx clerk@latest init` | — |
| **Convex** ([1](https://docs.convex.dev/ai)) | `llms.txt`, `convex_rules.txt` | Managed sections in `AGENTS.md`/`CLAUDE.md` + generated `guidelines.md` | Yes | — | Convex MCP | `npx convex ai-files install` | **Public evals repo** ([get-convex/convex-evals](https://github.com/get-convex/convex-evals)) + model leaderboard |
| **Prisma** ([1](https://www.prisma.io/docs/ai)) | `llms.txt`, `llms-full.txt` | Per-editor setup guides | `prisma/skills` | — | Remote `mcp.prisma.io/mcp` | `npx skills add prisma/skills` | — |
| **Cloudflare** ([1](https://developers.cloudflare.com/llms.txt)) | Root `llms.txt` → per-product `llms.txt`/`llms-full.txt` | — | Yes (agent setup page) | — | Yes | — | Authored the `.well-known/agent-skills` discovery RFC |
| **TanStack** ([Intent](https://tanstack.com/intent/latest)) | — | — | **Skills shipped inside npm packages** | — | — | Intent loads skills from `node_modules` after an explicit allowlist | "The skill releases with the code it explains"; `intent stale` flags skills whose source docs changed |

## 3. Keeping agent guidance in sync with API changes

Vendors use these mechanisms, roughly from cheapest to strongest:

1. **Generate from one source.** `llms.txt`, `llms-full.txt`, and `.md` pages are build outputs of the docs site, so they cannot drift from the HTML docs (Stripe, Vercel, Supabase, Cloudflare). Supabase auto-deploys its skills index from the skills repo.
2. **Version the guidance with the code.**
   - Next.js bundles version-matched docs in the `next` package, and its `AGENTS.md` block points there instead of at the web. Upgrading the package upgrades the docs.
   - TanStack Intent ships `SKILL.md` inside the npm package, so "the package version becomes the skill version."
   - This is the most robust answer to "the agent's training data is stale."
3. **Managed blocks, re-applied by tooling.** Next.js (`next dev`) and Convex (`ai-files update`) rewrite a delimited block in the consumer's `AGENTS.md`/`CLAUDE.md` and leave user content outside it alone.
4. **Auto-updating distribution.** Plugins update from their marketplace, for example Stripe's auto-updating plugin. Skills installed by copy (`npx skills add`) go stale unless the user updates them.
5. **Staleness detection.** TanStack `intent stale` flags a skill when a source file it declares has changed. The tool treats the flag as "a review signal, not proof of bad guidance."
6. **Evals in CI.**
   - Convex keeps a public evals repo.
   - Next.js publishes benchmark results and used them to choose `AGENTS.md` over skills.
   - Claude Code's [`claude plugin eval`](https://code.claude.com/docs/en/plugin-evals) runs prompt-plus-grader cases from `evals/`. Graders can be `regex`, `tool_used`, `tool_order`, `file_exists`, `llm`, or `baseline`. By default each case runs 3 times, and results are compared against a **no-plugin baseline**. You can gate CI with `--threshold`, and MCP tools can be mocked.
   - `claude plugin validate` checks the schema only, not behavior.
   - Anthropic's skill guidance says to write evals before writing extensive docs.

**Evidence on form factor.** [Vercel, "AGENTS.md outperforms skills in our agent evals"](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals) (Jude Gao, 2026-01-27) tested Next.js 16 APIs that are absent from training data:

| Condition | Pass rate |
|---|---|
| Baseline (no docs) | 53% |
| Skill, default | 53% (the skill was never invoked in 56% of cases) |
| Skill with explicit instructions to use it | 79% |
| `AGENTS.md` with a compressed docs index | 100% |

The compressed index was 8 KB, down from 40 KB. Vercel's conclusion: use always-on context for broad API knowledge, and use skills for explicit, vertical workflows ("upgrade", "migrate"). This is one vendor's eval on one framework, so treat it as directional.

## 4. TrueSeal-specific observations

### 4.1 Current state (read-only inspection)

- **Docs site** (`trueseal-docs`):
  - Astro 5 with MDX, React islands, sitemap, and Pagefind. It uses a custom layout rather than Starlight (ADR `0001-astro-over-starlight`).
  - Deployed on Cloudflare Pages, which builds on push to `main`. `site` is `https://trueseal.dev`.
  - Content is one `docs` content collection (`src/content/docs/**`, 28 `.mdx` files plus `license.md`) with a frontmatter schema of `title`, `description`, `order`. Pages render through `src/pages/docs/[...slug].astro`.
  - `public/` has only `robots.txt` and `favicon.svg`: no `llms.txt`, no `.md` exports.
  - MDX files use custom components. `<NextPage>` appears 28 times. `<Callout>`, `<FlowDiagram>`, `<CodeBlock>`, `<PhaseStack>`, and `<ManifestMember>` appear a few times each.
- **SDK API reference is not on the site.** `sdks.mdx` says "API reference, install instructions and integration examples live in each repo's README." Agent docs generated from the site alone would therefore cover concepts and protocol but not the Swift, Kotlin, or TypeScript API surface.
- **Existing agent files are for contributors, not consumers.** `trueseal-noise`, `trueseal-relay`, and `trueseal-sync` have a `CLAUDE.md`; `hush-clip-macos` has an `AGENTS.md`; the workspace root has an `AGENTS.md`. No SDK repo ships guidance meant for an app developer's agent.

### 4.2 What hosting `llms.txt` and Markdown exports would take in `trueseal-docs`

All of this is static and fits the current build; none of it needs SSR or a Cloudflare Function.

- **`src/pages/llms.txt.ts`:** a static endpoint ([Astro endpoints](https://docs.astro.build/en/guides/endpoints/)) that calls `getCollection('docs')` and emits the H1, blockquote summary, and H2 link lists grouped by folder (concepts, components, protocol, guides). It can reuse `src/config/nav.ts` for ordering, and would put `kitchen-sink` and `future` under `## Optional` or leave them out.
- **`src/pages/docs/[...slug].md.ts`:** a static endpoint with `getStaticPaths` over the same collection that returns each entry's raw `body`, with its title and description, as `text/markdown`. That serves `/docs/<slug>.md`, matching the Stripe and Next.js convention.
  - Catch: MDX bodies include `import` lines and JSX components. The endpoint needs a small transform that strips imports and replaces or removes components (`NextPage` → a plain link, `Callout` → a blockquote; `FlowDiagram`/`PhaseStack` need a text fallback or removal). Otherwise agents get noisy JSX.
- **`src/pages/llms-full.txt.ts`:** concatenates the same transformed bodies.
- **Optional extras:**
  - A `<link rel="alternate" type="text/markdown">` in `DocsLayout.astro`.
  - A "Copy as Markdown" button.
  - A `public/_headers` entry if Cloudflare serves `.md`/`.txt` with the wrong `Content-Type` (untested).
  - `Accept: text/markdown` negotiation would need a Pages Function or middleware, which adds runtime complexity for marginal gain.
- **Skills discovery:** a `/.well-known/agent-skills/index.json` could be emitted the same way if TrueSeal publishes skills. It needs a sha256 digest per artifact, computed at build time.
- **SDK API coverage:** either pull the SDK READMEs into the site at build time (git submodule or fetch step) or link to raw README URLs from `llms.txt`. The second option costs nothing but depends on GitHub availability and branch naming.

### 4.3 Properties that shape TrueSeal's choice

- TrueSeal is a local library with a self-hosted or public relay and **no hosted account state**. A vendor-style "live account" MCP server has little to expose, so the MCP value would be docs search only, which Context7 or `llms.txt` already give.
- TrueSeal is security-sensitive. The most useful agent guidance is **pitfalls**, not API listings:
  - Persist the Message ID and dedupe, since delivery is at least once.
  - Never treat relay acceptance as delivery.
  - Pairing needs explicit admission on both sides.
  - Payloads are opaque, and application versioning belongs to the app.
  - Don't log key material.

  This is the kind of content the Vercel eval showed works best when it is always present.
- There are three SDKs in three ecosystems. Package managers differ, so bundling docs in the package (the Next.js and TanStack pattern) means three packaging efforts:
  - npm packages carry files easily.
  - SwiftPM resources and Gradle artifacts are awkward for agents to locate.
- The project is pre-launch, which makes it cheap to set up an eval harness now, while the API is still changing.

## Options for TrueSeal

These are presented for decision in #19; this document does not choose between them. They are not mutually exclusive: most vendors layer A with one or more of B–E.

**A. Docs-site exports only (`llms.txt`, `llms-full.txt`, per-page `.md`).**
- Does: static Astro endpoints as in §4.2, plus a way to include SDK README content.
- Cost: low, one repo, fully generated, no drift from the docs.
- Limits: passive. Agents only use it when pointed at it, and it doesn't teach pitfalls unless the docs spell them out.

**B. Consumer-facing `AGENTS.md` snippet, managed-block style.**
- Does: a short, security-focused integration guide (pitfalls + link to `llms.txt`) that app developers paste or install into their own `AGENTS.md`, with a `CLAUDE.md` → `@AGENTS.md` shim. It could be written by a small `trueseal agents-md`-style command or an SDK helper, as Next.js and Convex do, or simply published as copy-paste text first.
- Cost: low for copy-paste; moderate with a CLI that upserts the block.
- Evidence: best-supported by Vercel's eval for API knowledge. Works in every agent that reads `AGENTS.md`.

**C. Agent Skills for integration workflows, distributed as a plugin/marketplace.**
- Does: a `trueseal-skills` repo (or a `skills/` folder in an existing repo) with a few workflow skills, e.g. "integrate TrueSeal sync into an app", "implement pairing UI with explicit admission", "add a relay for local dev". The same repo doubles as a Claude Code marketplace (`.claude-plugin/marketplace.json`), is installable cross-agent via `npx skills add`, and can optionally publish `/.well-known/agent-skills/index.json` from the docs site.
- Cost: moderate. Needs evals to prove the skills trigger and help; the Vercel data shows default triggering is unreliable.

**D. Version-matched guidance shipped inside SDK packages.**
- Does: each SDK package carries its own `AGENTS.md`/skill and API notes, so the guidance always matches the installed version (the Next.js and TanStack Intent pattern).
- Cost: highest; three ecosystems.
- Fit: most natural for `trueseal-sync-ts` (npm), awkward for SwiftPM and Gradle.
- Benefit: the strongest guarantee against drift.

**E. Third-party indexes (Context7) and optionally a docs MCP server.**
- Does: submit the SDK repos and docs to Context7, with `context7.json` and the refresh GitHub Action, for near-free coverage in agents that already use it.
- MCP: a dedicated TrueSeal MCP server has little to offer without live account state. It could become relevant later, e.g. local relay or test-harness control for agents.

**Cross-cutting choice, whichever options are picked: sync and quality gate.**
1. Generate-only (build outputs from docs).
2. Plus a CI check that agent artifacts reference symbols and pages that still exist.
3. Plus behavioral evals (`claude plugin eval` or a harness in `trueseal-e2e`) that ask an agent to integrate an SDK against a real relay and grade the result.

Each level up adds model-call cost and maintenance but is the only one that catches guidance that is wrong rather than missing.
