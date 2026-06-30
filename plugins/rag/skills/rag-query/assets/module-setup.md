# Module Setup

Standalone self-registration for the **RAG Connector** module (code `rag`). Loaded when:
- The user passes `setup`, `configure`, or `install` as an argument, or
- `rag-query` runs normally but `rag_query.py` reports `config_missing` (no `rag.endpoint_url` / `rag.credential`).

Module identity (name, code, version) and the config variables come from `./assets/module.yaml` (sibling to this file).

## Config model

This project reads config through `{project-root}/_bmad/scripts/resolve_config.py` — a **four-layer TOML merge**. Setup writes to the two human-authored layers so installer-owned files are never rewritten:

- **`{project-root}/_bmad/custom/config.toml`** — shared, committable. Core keys at root (`output_folder`, `document_output_language`); module values under a `[rag]` table.
- **`{project-root}/_bmad/custom/config.user.toml`** — gitignored. `user_name`, `communication_language` at root; secrets (any module var with `user_setting: true`, i.e. `rag.credential`) under `[rag]`.
- **`{project-root}/_bmad/module-help.csv`** — registers module capabilities for the help system.

The merge scripts use an anti-zombie pattern: the existing `[rag]` table is removed before fresh values are written, so stale values never persist. `credential` is **never** written to `config.toml`.

`{project-root}` is a **literal token** in config _values_ — never substitute it there. It does NOT apply to the filesystem path _arguments_ passed to the scripts below: resolve those to the real project root before running, or the scripts reject the unresolved token with an error.

## Check Existing Config

1. Read `./assets/module.yaml` for module metadata and variable definitions (`code` is the module identifier).
2. If `{project-root}/_bmad/custom/config.toml` already has a `[rag]` table, tell the user this is a reconfiguration (update), not a fresh install.

If the user passed inline values (e.g. `accept defaults`, `endpoint is https://…, token is sk-…`), map them to config keys, use defaults for the rest, and skip prompting — but still show the confirmation summary at the end.

## Collect Configuration

Present all values together (with defaults in brackets) so the user can respond once, changing only what they want. Never tell the user to "press enter" — in chat they must type something.

**Default priority** (highest wins): existing config values > `./assets/module.yaml` defaults.

### Core Config (only if not already set in either config layer)

- `user_name` (default: BMad) — written to `config.user.toml` root
- language (default: English — one question sets both `communication_language` and `document_output_language`); `communication_language` → `config.user.toml` root
- `output_folder` (default: `{project-root}/_bmad-output`) → `config.toml` root

### Module Config

Ask for each variable in `./assets/module.yaml` that has a `prompt` field, using its default. Question types: text (`prompt`/`default`/optional `required`,`regex`,`example`), `single-select` (`value`/`label` list), `multi-select`, and `confirm` (boolean default). Only `endpoint_url` is required; `credential` is required unless `auth_type` is `none`. Apply any `result` template when storing. `credential` has `user_setting: true` → it goes to `config.user.toml` under `[rag]`, never to `config.toml`.

`extra_body` and `result_fields` are advanced TOML tables and are **not** prompted — `rag_query.py` has correct dict defaults. If the user needs them, point them at the `[rag.extra_body]` / `[rag.result_fields]` examples in `module.yaml`.

## Write Files

Write a temp JSON file with the answers as `{"core": {...}, "module": {...}}` (omit `core` if it already exists). Keep the literal `{project-root}` token inside config _values_. Then run both scripts (parallel-safe — different files). Replace `{project-root}` in the **path arguments** with the actual project root first.

```bash
python3 ./scripts/merge-config.py \
  --config-path "{project-root}/_bmad/custom/config.toml" \
  --user-config-path "{project-root}/_bmad/custom/config.user.toml" \
  --module-yaml ./assets/module.yaml --answers {temp-file}
python3 ./scripts/merge-help-csv.py \
  --target "{project-root}/_bmad/module-help.csv" \
  --source ./assets/module-help.csv --module-code rag
```

Both print JSON to stdout. If either exits non-zero, surface the error and stop. Run with `--help` for full usage.

## Create Output Directories

Resolve `{project-root}` and create any path-type config value that doesn't exist yet (e.g. `output_folder`, plus any `[rag]` value starting with `{project-root}/`). The stored config keeps the literal token; only the on-disk directories use the resolved path. Use `mkdir -p`.

## Confirm

From the script JSON, show what was written (config.toml `[rag]` keys, config.user.toml `user_keys`, help entries added, fresh-install vs update). If `./assets/module.yaml` has `post-install-notes`, display them. Then display the `module_greeting` from `module.yaml`.

## Return to Skill

Setup is complete. Resume `rag-query`'s normal flow — `rag_query.py` will now resolve the `[rag]` config and run the query the user originally asked for.
