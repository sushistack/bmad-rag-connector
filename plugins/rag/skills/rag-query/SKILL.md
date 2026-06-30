---
name: rag-query
description: Query a configured external RAG endpoint for ranked passages. Use when the user says "/rag-query", "search the RAG", "query the knowledge base", "pull RAG context", or asks to ground the session in retrieved passages.
---

# rag-query

Use when the user wants to ground an answer in passages retrieved from their external RAG service. This skill implements no backend — the endpoint, auth, request shape, and response parsing all come from the `[rag]` config table, so it is the config (not code) that adapts to whichever service is on the other end. Returns ranked passages as plain conversational text.

## On activation

This skill is a self-registering standalone module (module code `rag`). Before anything else:

- If the user passed `setup`, `configure`, or `install`, load `./assets/module-setup.md` and complete registration first. This always runs, even when already configured (for reconfiguration).
- Otherwise proceed to the normal query flow. If `rag_query.py` returns `status: config_missing`, the module isn't configured yet — offer to run `./assets/module-setup.md`, then retry the query.

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

- **`ok`** — render `results` for the user: each passage's `text` with its `source` (and `score` if present), as a short readable list. Lead with the `count` field. Do not dump the raw JSON.
- **`config_missing`** — the endpoint or credential isn't set. Tell the user exactly what `missing` lists and where `where` says to put it (see Configuration), then stop. This is the expected first-run state.
- **`request_error`** / **`parse_error`** — surface `error` (and `body`/`raw` if present) plainly. A `parse_error` almost always means `rag.results_path` or `rag.result_fields` don't match the service's response shape — point the user at those keys.

## Activation modes

- **Interactive** — the user runs `/rag-query` or asks in natural language. If they didn't give a query string, ask for one. If they named a result count, pass it as `--top-k`.
- **Headless** — called with a `query` (and optional `top_k`). Run the script with those args and return its JSON unchanged; do not add conversational rendering.

## Configuration

There are two ways to supply config. `rag_query.py` reads the BMad TOML resolver first, then overlays `RAG_*` environment variables (**env wins**), so the endpoint and credential are always settable — even with no BMad install.

### Option A — environment variables (works anywhere, no BMad needed)

The simplest path when running as a plugin in a non-BMad project:

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

### Option B — BMad TOML config

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

## Gotchas
- **Config is TOML** (`config.toml` / `config.user.toml`), not YAML.
- **`top_k` is sent as a body field named `top_k`.** A service that names it differently (`k`, `limit`, `num_results`) should set that field via `rag.extra_body`.
- **`bearer` always uses the `Authorization` header** (`Bearer <credential>`) and ignores `auth_header_name`; `api_key` and `custom_header` use `auth_header_name` with the raw credential.
