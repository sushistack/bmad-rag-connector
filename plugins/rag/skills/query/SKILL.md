---
name: query
description: Query a configured external RAG endpoint for ranked passages. Use when the user says "/rag:query", "search the RAG", "query the knowledge base", "pull RAG context", or asks to ground the session in retrieved passages.
---

# query

Use when the user wants to ground an answer in passages retrieved from their external RAG service. This skill implements no backend — the endpoint, auth, request shape, and response parsing all come from the `[rag]` config table, so it is the config (not code) that adapts to whichever service is on the other end. Returns ranked passages as plain conversational text.

## On activation

This skill is a self-registering standalone module (module code `rag`). Before anything else:

- If the user passed `setup`, `configure`, or `install` in a BMad project, load `./assets/module-setup.md` and complete registration first. This always runs, even when already configured (for reconfiguration).
- Otherwise proceed to the normal query flow. If `rag_query.py` returns `status: config_missing`, the module isn't configured — **do not query; show the setup guide** (see the `config_missing` handling below) and stop.

## Resolution rules
- `{skill-root}` → this skill's installed directory; `scripts/rag_query.py` resolves from it.
- `{project-root}` → the project working directory.

## How it works

One deterministic script carries the whole call: `scripts/rag_query.py` reads the merged `[rag]` config, assembles the request (method, auth header, JSON body with the query injected), calls the endpoint, and parses the response by config-driven JSON paths. Your job is only to run it, then **render the returned passages conversationally** — and, when config is missing, relay the fix.

Run it with the project root and the user's query:

```bash
uv run {skill-root}/scripts/rag_query.py \
  --project-root {project-root} --query "<the user's query>" [--top-k N]
```

It prints one JSON object with a `status` field. Handle each status:

- **`ok`** — two shapes, distinguished by `mode`:
  - `mode: "passages"` — render `results`: each passage's `text` with its `source` (and `score` if present) as a short readable list; lead with `count`. Don't dump raw JSON.
  - `mode: "answer"` — the endpoint is a generative RAG that already synthesized a reply. Render the `answer` string directly. (No passages to list.)
- **`config_missing`** — only the endpoint is missing (a credential is optional). **Do not attempt the query.** Show the user how to set the endpoint, leading with the slash command:
  - `/rag:set-endpoint <url>` — set the RAG endpoint URL
  - `/rag:set-token <token>` — **optional**, only if the endpoint needs auth
  - Alternatives: export `RAG_ENDPOINT_URL` (and `RAG_CREDENTIAL` if needed), the plugin config prompt, or (BMad projects) the `[rag]` TOML keys.

  Then stop and let the user configure. This is the expected first-run state.
- **`request_error`** / **`parse_error`** — surface `error` (and `body`/`raw` if present) plainly. A `parse_error` means the response matched neither a passages list nor an answer string — point the user at `rag.results_path` (retrieval APIs) or `rag.answer_field` (generative APIs).

## Activation modes

- **Interactive** — the user runs `/rag:query` or asks in natural language. If they didn't give a query string, ask for one. If they named a result count, pass it as `--top-k`.
- **Headless** — called with a `query` (and optional `top_k`). Run the script with those args and return its JSON unchanged; do not add conversational rendering.

## Configuration

Config is layered, lowest to highest priority: **BMad TOML → env vars → slash-command override file**. Only `endpoint_url` is required; a credential is **optional** (sent only when set — endpoints that need no auth just work). The response shape is auto-detected: a passages list (`results_path`) or a generated `answer` string (`answer_field`, default `answer`) for generative RAG endpoints like alpha-hrag. `top_k` is sent only when set (`--top-k` or `rag.top_k`) — some APIs reject unknown body fields.

### Option A — plugin config prompt (GUI, easiest when installed as a plugin)

When this is installed as a Claude Code plugin, enabling it prompts the user for **RAG endpoint URL**, **RAG credential** (masked), and **auth type** (declared in `plugin.json` `userConfig`). Claude Code exports those to every subprocess as `CLAUDE_PLUGIN_OPTION_RAG_ENDPOINT_URL` / `_RAG_CREDENTIAL` / `_RAG_AUTH_TYPE`, and `rag_query.py` reads them automatically. No shell export, no file editing.

### Slash commands (set config from chat, no GUI needed)

Persist config without editing files or the shell — useful when the plugin config prompt isn't available:

- `/rag:set-endpoint <url>` — set (or, with no argument, clear) the endpoint URL
- `/rag:set-token <token>` — set (or clear) the credential ⚠️ *the token appears in the chat transcript; prefer the GUI prompt or `RAG_CREDENTIAL` env for secrets when you can*

These write to `${CLAUDE_PLUGIN_DATA}/config-override.json` (`chmod 600`, outside the repo) — the **highest-priority** config layer, so they win over env and TOML.

### Option B — environment variables (works anywhere, incl. non-plugin use)

Set them yourself; a manual `RAG_*` also overrides the plugin-prompt value for a one-off switch:

```bash
export RAG_ENDPOINT_URL="https://rag.example.com/search"   # required
export RAG_CREDENTIAL="sk-..."                             # API key / bearer token (secret)
# optional overrides (sensible defaults otherwise):
export RAG_AUTH_TYPE="bearer"        # none | api_key | bearer | custom_header
export RAG_METHOD="POST"
export RAG_AUTH_HEADER_NAME="Authorization"
export RAG_QUERY_FIELD="query"
export RAG_TOP_K="5"
export RAG_RESULTS_PATH="results"
export RAG_EXTRA_BODY='{"index":"docs"}'                   # JSON object
export RAG_RESULT_FIELDS='{"text":"text","source":"meta.url","score":"score"}'  # JSON object
```

`RAG_ENDPOINT_URL` + `RAG_CREDENTIAL` are the only ones most services need. These also override BMad config for a one-off endpoint switch.

### Option C — BMad TOML config

In a BMad project, config lives under module code `rag`. Shared values go in `{project-root}/_bmad/config.toml` (committable); the secret goes in `{project-root}/_bmad/config.user.toml` (gitignored). The script reads them through the project's resolver, so the four-layer merge and defaults apply.

```toml
# _bmad/config.toml  — shared, committable
[rag]
endpoint_url     = "https://rag.example.com/search"  # required
method           = "POST"                            # default POST
auth_type        = "bearer"                          # none | api_key | bearer | custom_header
auth_header_name = "Authorization"                   # header for api_key / custom_header
query_field      = "query"                           # body field carrying the query text
top_k            = 5                                 # default result count
results_path     = "results"                         # dotted path to the results array
[rag.extra_body]                                     # static fields merged into the body (filters, index)
[rag.result_fields]                                  # output field -> response field (dotted ok)
text   = "text"
source = "source"
score  = "score"
```

```toml
# _bmad/config.user.toml  — gitignored, secret
[rag]
credential = "sk-..."   # API key or bearer token; required unless auth_type = none
```

Defaults are sensible: a typical `POST {url}` JSON RAG API that returns `{ "results": [ {text, source, score} ] }` needs only `endpoint_url` + `credential`.

**Point it at a different RAG service** by editing config alone: change `endpoint_url` + `credential`, set `auth_type` to match, and map the response with `results_path` (where the array lives, e.g. `data.hits`) and `result_fields` (which response fields become text/source/score, dotted paths like `meta.url` allowed). Python changes are needed only if a service's response is too irregular for path-mapping — that's the one place a small per-service adapter could be added later; call it out, don't build it speculatively.

## Generative RAG (answer mode)

Some endpoints (e.g. NHN alpha-hrag `/api/v1/retrieve`) don't return passages — they return a synthesized `answer` string plus doc ids. This is handled automatically: if the response has no list at `results_path`, the script reads `answer_field` (default `answer`) and returns `mode: "answer"`. Such endpoints also often forbid unknown body fields, which is why `top_k` is omitted unless you set it. For alpha-hrag, **setting only the endpoint is enough** (no token, no top_k). If the answer field has another name, set `answer_field` (env `RAG_ANSWER_FIELD`).

## Gotchas
- **Only `endpoint_url` is required.** A credential is optional — without one, no auth header is sent. `top_k` is sent only when set.
- **Config is TOML** (`config.toml` / `config.user.toml`), not YAML.
- **`top_k`, when set, is a body field named `top_k`.** A service that names it differently (`k`, `limit`) should set that field via `rag.extra_body` instead and leave `top_k` unset.
- **`bearer` uses the `Authorization` header** (`Bearer <credential>`) and ignores `auth_header_name`; `api_key` / `custom_header` use `auth_header_name`. With no credential, no header is sent regardless of `auth_type`.
