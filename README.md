# bmad-rag-connector

A thin, configurable **RAG connector** packaged as a Claude Code plugin (and a self-registering BMad module). It does **not** implement any retrieval backend — no embeddings, vector store, or chunking. It sends a query to an endpoint you configure and returns the ranked passages.

The endpoint URL, auth, request shape, and response parsing are all injected through config, so pointing the connector at a different RAG service — an internal corporate one or a public docs API — is a **config edit, never a code change**.

## What you get

- One skill, `query`: query in → ranked passages out (text + source + score), rendered conversationally.
- Config-driven adapter: swap services by editing `[rag]` config keys.
- Secrets isolation: the credential lives only in a gitignored config file, never in committed config.

## Requirements

- A project that uses BMad's TOML config resolver (`_bmad/scripts/resolve_config.py`).
- `uv` (the skill's scripts run via `uv run`).
- `curl`-style HTTP reachability to your RAG endpoint (calls go out over `urllib`). No SDK, no extra packages.

## Install

```shell
/plugin marketplace add sushistack/bmad-rag-connector
/plugin install rag@bmad-rag-connector
```

After install the skill is invoked as `/rag:query`.

## Configure

`rag_query.py` reads the BMad TOML resolver first, then overlays env vars (**env wins**). The endpoint + credential are always settable, three ways:

### Option A — plugin config prompt (easiest)

When installed as a Claude Code plugin, enabling it pops up a form asking for **RAG endpoint URL**, **RAG credential** (masked), and **auth type** — declared via `userConfig` in `plugin.json`. Claude Code exports them to subprocesses as `CLAUDE_PLUGIN_OPTION_RAG_*`, which the script reads automatically. Nothing to edit by hand.

### Slash commands (set from chat, no GUI needed)

- `/rag:set-endpoint <url>` — set (or clear) the endpoint URL **(this is all you need for a no-auth endpoint)**
- `/rag:set-token <token>` — **optional**, only if your endpoint needs auth ⚠️ *the token is written to the chat transcript; prefer the config prompt or `RAG_CREDENTIAL` env for secrets*

These persist to `${CLAUDE_PLUGIN_DATA}/config-override.json` (`chmod 600`) and are the highest-priority config layer. Only the endpoint is required to run; if it's unset, the skill stops and shows these instructions instead.

### Generative RAG (answer mode)

If your endpoint returns a synthesized **answer** (not a passages list) — e.g. NHN alpha-hrag `/api/v1/retrieve` — it's auto-detected: set only the endpoint and the skill returns the `answer`. No token, no `top_k` (that endpoint rejects extra body fields, so `top_k` is sent only when you set it). Override the field name with `RAG_ANSWER_FIELD` if it isn't called `answer`.

### Option B — environment variables (no BMad install needed)

Set them yourself (also overrides the plugin prompt for a one-off switch):

```bash
export RAG_ENDPOINT_URL="https://rag.example.com/search"   # required
export RAG_CREDENTIAL="sk-..."                             # API key / bearer token (secret)
# optional: RAG_AUTH_TYPE, RAG_METHOD, RAG_AUTH_HEADER_NAME, RAG_QUERY_FIELD,
#           RAG_TOP_K, RAG_RESULTS_PATH, RAG_EXTRA_BODY (JSON), RAG_RESULT_FIELDS (JSON)
```

`RAG_ENDPOINT_URL` + `RAG_CREDENTIAL` are all most services need. These also override BMad config for a one-off endpoint switch.

### Option C — BMad TOML config

In a BMad project, run the skill with `setup` (or just run a query — if config is missing it offers to configure):

```shell
/rag:query setup
```

This writes to the project's TOML config (human-authored resolver layers):

```toml
# _bmad/custom/config.toml  — shared, committable
[rag]
endpoint_url     = "https://rag.example.com/search"  # required
method           = "POST"                            # POST | GET
auth_type        = "bearer"                          # none | api_key | bearer | custom_header
auth_header_name = "Authorization"                   # header for api_key / custom_header
query_field      = "query"                           # body field that carries the query text
top_k            = 5                                 # default result count
results_path     = "results"                         # dotted path to the results array

[rag.extra_body]                                     # optional static body fields (filters, index)
# index = "docs"

[rag.result_fields]                                  # output field -> response field (dotted ok)
text   = "text"
source = "source"
score  = "score"
```

```toml
# _bmad/custom/config.user.toml  — gitignored, secret
[rag]
credential = "sk-..."   # API key or bearer token; required unless auth_type = "none"
```

A typical `POST {url}` JSON API that returns `{ "results": [ {text, source, score} ] }` needs only `endpoint_url` + `credential`.

## Point it at a different RAG service

Edit config alone — no code:

1. Set `endpoint_url` + `credential`, and `auth_type` to match the service.
2. Map the response: `results_path` (where the array lives, e.g. `data.hits`) and `result_fields` (which response fields become text/source/score — dotted paths like `meta.url` are allowed).

Python changes are only needed if a service's response is too irregular for path-mapping — that's the one place a small per-service adapter would go.

## Usage

```shell
/rag:query how do refunds work?
/rag:query "billing edge cases" --top-k 8
```

Headless: the underlying script can be called directly and returns one JSON object (`status` ∈ `ok` / `config_missing` / `request_error` / `parse_error`).

## License

MIT — see [LICENSE](LICENSE).
