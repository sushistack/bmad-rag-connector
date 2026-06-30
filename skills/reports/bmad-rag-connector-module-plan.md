---
title: 'BMad RAG Connector — Module Plan'
status: 'complete'
module_name: 'RAG Connector'
module_code: 'rag'
module_description: 'A thin, configurable connector that sends queries to an external RAG service and returns results — endpoint/auth/schema are injected via config, not hardcoded.'
architecture: 'standalone single workflow skill'
standalone: true
expands_module: ''
skills_planned: ['rag-query']
config_variables: ['rag.endpoint_url', 'rag.method', 'rag.auth_type', 'rag.auth_header_name', 'rag.query_field', 'rag.extra_body', 'rag.results_path', 'rag.result_fields', 'rag.top_k', 'rag.credential']
created: '2026-06-30'
updated: '2026-06-30'
---

# Module Plan

## Vision

A standalone BMad module (`bmad-rag-connector`) that acts as a **thin connector** to an
already-existing external RAG service. It does NOT implement any RAG backend (no embeddings,
vector DB, or chunking) — it sends a query to a configured endpoint and returns the results.

The endpoint URL, auth method, and request/response schema are all **injected via config**, so
swapping endpoint + credentials lets the same module serve an internal corporate RAG or any
general-purpose RAG service without touching core logic. No company or RAG implementation is
hardcoded.

**Who it's for:** the author and their team — anyone who wants to pull RAG context into a BMad
session without standing up their own retrieval layer.

**Constraints (from init-prompt.md):**
- Do not modify bmad-method core (read-only).
- Build via BMB: IM → BA/BW → CM → VM.
- Story-sized work — no PRD/epic split.
- Endpoint/auth/response-schema separated as config; replaceable without code edits.
- Secrets live in `config.user.yaml` (gitignored); shared config in `config.yaml`.

## Architecture

**Decision:** A single **workflow skill** (`rag-query`) in a standalone module.

**Rationale:**
- The module has exactly one capability — take a query, call a configured RAG endpoint, return
  results. There is no persistent persona and no value in cross-session memory, so an agent would
  add ceremony without benefit.
- Standalone single-skill: per BMB, CM embeds self-registration directly into the skill (no separate
  `-setup` skill is generated).
- Invocation is **explicit / description-triggered** by the user. Auto-invocation from inside another
  bmad-method core workflow is intentionally out of scope, because wiring that in would require
  editing a core skill — forbidden by the "core is read-only" constraint. A future *new* module may
  call `rag-query` from its own skill; nothing here prevents that.

### Memory Architecture

**None.** The skill is stateless — each invocation reads config, calls the endpoint, returns results.
No personal or shared memory folder is needed.

### Memory Contract

N/A — no memory.

### Cross-Agent Patterns

N/A — single skill, no agents. The user is the only "router": they invoke `rag-query`, then use the
returned passages in whatever they were doing.

## Skills

### rag-query

**Type:** workflow

**Persona:** N/A (stateless workflow, no persona).

**Core Outcome:** The user gets relevant passages back from their configured RAG service, with
source metadata, ready to use in the current session — without the module knowing or caring which
RAG backend is on the other end.

**The Non-Negotiable:** Endpoint URL, auth, request shape, and response parsing are **never
hardcoded** — all come from config. Pointing the module at a different RAG service must be a
config edit only, zero code changes.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| query-rag | Send the user's query to the configured RAG endpoint and return ranked results to the session | `query` (string, required); optional `top_k` override | Ranked passages — each with text + source metadata (title/url/score as mapped by config), rendered as plain conversational output. (An HTML report is explicitly deferred — see Design Notes.) |

**Memory:** None — reads config on each run, writes nothing.

**Init Responsibility:** On invocation, check that `rag.endpoint_url` (and `rag.credential` if
`auth_type` requires one) are set. If missing, stop and guide the user to fill in
`_bmad/config.yaml` / `_bmad/config.user.yaml`. This missing-config check is the practical entry
point for the internal↔general reuse story.

**Activation Modes:** Both. Interactive (user runs `/rag-query` or asks in natural language) and
headless (callable with `query`/`top_k` args for scripted use).

**Tool Dependencies:** `curl` (HTTP call via Bash) — no new npm package, no SDK. The skill reads
config, assembles the request (URL, method, auth header, body from a template with the query
injected), runs `curl`, then parses the response using config-driven JSON paths.

**Design Notes:**
- **Adapter boundary = config, not code.** `rag.results_path` (JSON path to the results array) and
  `rag.result_fields` (map of output field → response field) describe how to read an arbitrary RAG
  response. The "expected response format" is documented so swapping services means editing these
  values. If a service's shape is too irregular for path-mapping, that's the one place a small
  per-service adapter snippet could be added later — call it out, don't build it speculatively.
- **Secrets isolation.** `rag.credential` lives in `config.user.yaml` (gitignored); everything else
  in `config.yaml` (committable).
- **Auth generalization.** `auth_type` ∈ {none, api_key, bearer, custom_header}; for `custom_header`,
  `auth_header_name` names the header. Covers the common cases; corporate SSO would be a future
  extension noted in the README.
- **`npm package?` (user's open question):** No. A BMad skill is markdown + config; packaging as npm
  adds a build/publish surface with no payoff for this use. Documented and dismissed.
- **HTML report deferred (user decision):** Initial build returns plain conversational results only.
  HTML report is a future enhancement, not in scope now.
- **Single capability confirmed (user decision):** No result-summarization or multi-query batch in
  v1 — query in, ranked passages out. Add later only if a real need appears.

---

## Configuration

Config keys live under module code `rag`. Shared, committable values in `_bmad/config.yaml`; the
secret in `_bmad/config.user.yaml`.

| Variable | Prompt | Default | Result Template | User Setting |
| -------- | ------ | ------- | --------------- | ------------ |
| `rag.endpoint_url` | RAG service endpoint URL | _(none — required)_ | `rag.endpoint_url` | No (config.yaml) |
| `rag.method` | HTTP method | `POST` | `rag.method` | No |
| `rag.auth_type` | Auth type: none / api_key / bearer / custom_header | `bearer` | `rag.auth_type` | No |
| `rag.auth_header_name` | Header name when auth_type=custom_header (or api_key) | `Authorization` | `rag.auth_header_name` | No |
| `rag.query_field` | JSON body field that carries the query text | `query` | `rag.query_field` | No |
| `rag.extra_body` | Extra static JSON merged into the request body (filters, index name, etc.) | `{}` | `rag.extra_body` | No |
| `rag.top_k` | Default number of results to request | `5` | `rag.top_k` | No |
| `rag.results_path` | JSON path to the results array in the response | `results` | `rag.results_path` | No |
| `rag.result_fields` | Map: output field → response field (e.g. text, source, score) | `{text: text, source: source, score: score}` | `rag.result_fields` | No |
| `rag.credential` | API key / bearer token (secret) | _(none)_ | `rag.credential` | **Yes (config.user.yaml)** |

Defaults are sensible enough that pointing at a typical `POST {url}` JSON RAG API needs only
`endpoint_url` + `credential`. Skill must fall back to these defaults and ask at runtime for any
required value that's missing.

## External Dependencies

`curl` only (present on macOS/Linux by default). No MCP server, no SDK, no npm package. The setup
flow does not need to install anything — it only needs to confirm `endpoint_url`/`credential` are
populated.

## UI and Visualization

None for the initial build. Results are returned as plain conversational text. An **HTML results
report** (passages + sources + scores as a shareable browsable file) is a recognized future
enhancement but is **deferred** by user decision — do not build it now.

## Setup Extensions

For a standalone single-skill module, CM embeds self-registration into the skill rather than
generating a separate setup skill. The only setup behavior needed: on first run, detect empty
`endpoint_url`/`credential` and walk the user through filling them in. No directory scaffolding,
no external service install, no starter files.

## Integration

Standalone. Provides independent value the moment config points at any RAG endpoint. Registers into
`bmad-help` under module `bmad-rag-connector`. No parent module. A future module could call
`rag-query` from its own (new) skill without modifying core.

## Creative Use Cases

- **Multi-endpoint switching by config profile** — point `config.yaml` at the corporate RAG, swap to
  a public docs RAG by editing endpoint + credential. Same skill, different knowledge base.
- **Inline grounding** — during any BMad conversation, run `/rag-query` to pull authoritative
  passages before writing a doc or answering, instead of relying on model memory.
- **HTML report for sharing** — emit the results report as a standalone browsable artifact for a
  teammate.

## Ideas Captured

Raw context distilled from `docs/init-prompt.md` (the user's spec for this module):

- **Thin connector, not a backend.** Module sends a query to an existing RAG endpoint and returns
  results. No embeddings/vector DB/chunking implemented here.
- **Endpoint-agnostic by config.** URL + auth + request/response schema all injected; swapping
  config switches between an internal corporate RAG and any general RAG service.
- **Config split.** Shared, git-committed values in `_bmad/config.yaml` (keyed by module code);
  secrets (API keys) in `_bmad/config.user.yaml` (gitignored).
- **Response adapter boundary.** Response shapes differ per RAG service, so parsing should be an
  adapter (or at minimum a documented "expected response format") — making the swap point explicit.
- **Setup checks for missing endpoint/auth** and guides the user to fill it in — this is the real
  entry point for the internal↔general reuse story.
- **Reusability documented** — README/module description includes a one-paragraph "how to point
  this at a different RAG endpoint."
- **Open question raised by the user:** "should this be an npm package?" — likely no for a BMad
  skill, but noted.
- **No prior art:** a generic "call external RAG API" connector module does not exist in the
  bmad-method ecosystem (closest, `bmad-aisg-aiml`, is an ML-methodology pack, not a connector).
  Re-confirm before building; build new if still absent.

_Resolved decisions (Phase 3–6): workflow skill (not agent); no concrete RAG service yet → generic
config scaffold; explicit/description-triggered invocation only (auto-call from core is out of scope
under the read-only constraint); auth generalized via `auth_type` + credential field; response
adapter = config-driven `results_path` + `result_fields`; single capability; HTML report deferred._

## Build Roadmap

Single skill, so the order is trivial — but the BMB sequence still matters:

1. **Build `rag-query` (Build a Workflow / BW)** — the only skill. Hand this plan as context. Key
   requirements to pass the builder: config-driven endpoint/auth/body/response (no hardcoding),
   `curl`-based call, missing-config check on run, optional HTML report output, both interactive and
   headless activation.
2. **Create Module (CM)** — package as a standalone single-skill module; CM embeds self-registration
   (no separate `-setup` skill), and generates `marketplace.json` / `module.yaml` / `module-help.csv`
   / `assets/module-setup.md`. Verify relative paths in `marketplace.json`.
3. **Validate Module (VM)** — check structural integrity and registration quality; fix and re-run
   until clean.

**Next steps:**

1. Build `rag-query` using **Build a Workflow (BW)** — share this plan document as context
2. Return to **Create Module (CM)** to scaffold the module infrastructure
3. Run **Validate Module (VM)** to verify
