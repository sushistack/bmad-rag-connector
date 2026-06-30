# bmad-rag-connector

A thin, configurable **RAG connector** packaged as a Claude Code plugin (and a self-registering BMad module). It does **not** implement any retrieval backend — no embeddings, vector store, or chunking. It sends a query to an endpoint you configure and returns the ranked passages.

The endpoint URL, auth, request shape, and response parsing are all injected through config, so pointing the connector at a different RAG service — an internal corporate one or a public docs API — is a **config edit, never a code change**.

## What you get

- One skill, `rag-query`: query in → ranked passages out (text + source + score), rendered conversationally.
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

After install the skill is invoked as `/rag:rag-query`.

## Configure

Run the skill with `setup` (or just run a query — if config is missing it offers to configure):

```shell
/rag:rag-query setup
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
/rag:rag-query how do refunds work?
/rag:rag-query "billing edge cases" --top-k 8
```

Headless: the underlying script can be called directly and returns one JSON object (`status` ∈ `ok` / `config_missing` / `request_error` / `parse_error`).

## License

MIT — see [LICENSE](LICENSE).
