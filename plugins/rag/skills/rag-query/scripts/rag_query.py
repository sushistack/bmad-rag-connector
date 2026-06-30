#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
rag-query — send a query to a configured external RAG endpoint and return ranked passages.

Everything here is deterministic plumbing: read config, assemble the request, call the
endpoint, parse the response by config-driven JSON paths, print results as JSON. No RAG
backend is implemented — the endpoint, auth, request shape, and response parsing all come
from the `[rag]` config table, so pointing at a different service is a config edit only.

Config is read through the project's canonical resolver
(`{project-root}/_bmad/scripts/resolve_config.py`, four-layer TOML merge, stdlib only),
so this script adds no new dependency. Stdlib-only (urllib, json, subprocess).

Usage:
  uv run rag_query.py --project-root /abs/proj --query "how do refunds work?"
  uv run rag_query.py --project-root /abs/proj --query "..." --top-k 8

Output: one JSON object on stdout. `status` is one of:
  ok            results array populated (exit 0)
  config_missing required config absent — `missing` lists what to set, `where` names the file (exit 2)
  request_error endpoint call failed — `error` carries the detail (exit 3)
  parse_error   response parsed but results_path/result_fields didn't match — `error` + `raw` sample (exit 3)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULTS = {
    "method": "POST",
    "auth_type": "bearer",
    "auth_header_name": "Authorization",
    "query_field": "query",
    "extra_body": {},
    "top_k": 5,
    "results_path": "results",
    "result_fields": {"text": "text", "source": "source", "score": "score"},
}
AUTH_NEEDS_CREDENTIAL = {"api_key", "bearer", "custom_header"}


def emit(obj: dict, code: int) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    sys.exit(code)


# RAG_* env var -> cfg key. These overlay (and win over) the BMad resolver, so the
# endpoint and credential are always settable — even with no BMad install at all.
_ENV_MAP = {
    "RAG_ENDPOINT_URL": "endpoint_url",
    "RAG_METHOD": "method",
    "RAG_AUTH_TYPE": "auth_type",
    "RAG_AUTH_HEADER_NAME": "auth_header_name",
    "RAG_QUERY_FIELD": "query_field",
    "RAG_TOP_K": "top_k",
    "RAG_RESULTS_PATH": "results_path",
    "RAG_CREDENTIAL": "credential",
    "RAG_EXTRA_BODY": "extra_body",        # JSON object string
    "RAG_RESULT_FIELDS": "result_fields",  # JSON object string
}


def _resolver_config(project_root: Path) -> dict:
    """Merged `[rag]` table from the project's BMad TOML resolver. {} if unavailable.

    Never exits — a missing resolver just means "no BMad config here", in which case
    env vars (or the top-k arg) supply everything. main() decides what's required.
    """
    resolver = project_root / "_bmad" / "scripts" / "resolve_config.py"
    if not resolver.exists():
        return {}
    try:
        proc = subprocess.run(
            ["uv", "run", str(resolver), "-p", str(project_root), "-k", "rag"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if proc.returncode != 0:
        return {}
    try:
        return (json.loads(proc.stdout or "{}")).get("rag", {}) or {}
    except json.JSONDecodeError:
        return {}


def _env_config() -> dict:
    """Read RAG_* environment variables into a cfg dict. Works with no BMad install."""
    cfg: dict = {}
    for env_key, cfg_key in _ENV_MAP.items():
        raw = os.environ.get(env_key)
        if not raw:
            continue
        if cfg_key == "top_k":
            try:
                cfg[cfg_key] = int(raw)
            except ValueError:
                pass  # ponytail: ignore non-int RAG_TOP_K; --top-k arg / DEFAULTS still apply
        elif cfg_key in ("extra_body", "result_fields"):
            try:
                cfg[cfg_key] = json.loads(raw)
            except json.JSONDecodeError:
                pass  # ponytail: malformed JSON env → skip, fall back to DEFAULTS dict
        else:
            cfg[cfg_key] = raw
    return cfg


def load_rag_config(project_root: Path) -> dict:
    """`[rag]` config: BMad resolver as base, RAG_* env vars overlaid on top (env wins)."""
    cfg = _resolver_config(project_root)
    cfg.update(_env_config())
    return cfg


def dig(obj, dotted: str):
    """Follow a dotted path through nested dicts. Returns None on any miss."""
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def build_request(cfg: dict, query: str, top_k: int):
    url = cfg.get("endpoint_url")
    method = str(cfg.get("method", DEFAULTS["method"])).upper()
    query_field = cfg.get("query_field", DEFAULTS["query_field"])
    extra_body = cfg.get("extra_body", DEFAULTS["extra_body"]) or {}

    # ponytail: top_k always sent under the field "top_k"; a service that names it
    # differently (k / limit / num_results) sets that field via rag.extra_body instead.
    body = dict(extra_body)
    body[query_field] = query
    body["top_k"] = top_k

    headers = {"Content-Type": "application/json"}
    auth_type = cfg.get("auth_type", DEFAULTS["auth_type"])
    header_name = cfg.get("auth_header_name", DEFAULTS["auth_header_name"])
    cred = cfg.get("credential")
    if auth_type == "bearer":
        headers["Authorization"] = f"Bearer {cred}"
    elif auth_type in ("api_key", "custom_header"):
        headers[header_name] = cred

    data = json.dumps(body).encode("utf-8")
    return urllib.request.Request(url, data=data, headers=headers, method=method)


def parse_response(payload: dict, cfg: dict) -> list:
    results_path = cfg.get("results_path", DEFAULTS["results_path"])
    result_fields = cfg.get("result_fields", DEFAULTS["result_fields"])
    rows = dig(payload, results_path)
    if not isinstance(rows, list):
        raise ValueError(
            f"results_path '{results_path}' did not point to a list "
            f"(got {type(rows).__name__}). Check rag.results_path against the response shape."
        )
    out = []
    for row in rows:
        out.append({out_key: dig(row, resp_path) for out_key, resp_path in result_fields.items()})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Query a configured external RAG endpoint.")
    ap.add_argument("--project-root", "-p", required=True)
    ap.add_argument("--query", "-q", required=True)
    ap.add_argument("--top-k", type=int, default=None, help="Override rag.top_k for this call.")
    args = ap.parse_args()

    project_root = Path(args.project_root).resolve()
    cfg = load_rag_config(project_root)

    missing = []
    if not cfg.get("endpoint_url"):
        missing.append("rag.endpoint_url")
    auth_type = cfg.get("auth_type", DEFAULTS["auth_type"])
    if auth_type in AUTH_NEEDS_CREDENTIAL and not cfg.get("credential"):
        missing.append("rag.credential")
    if missing:
        emit({
            "status": "config_missing",
            "missing": missing,
            "where": ("export env vars RAG_ENDPOINT_URL / RAG_CREDENTIAL (works anywhere, "
                      "no BMad needed); or in a BMad project set rag.endpoint_url in "
                      "_bmad/custom/config.toml under [rag] and rag.credential in "
                      "_bmad/custom/config.user.toml (gitignored)"),
        }, 2)

    top_k = args.top_k if args.top_k is not None else cfg.get("top_k", DEFAULTS["top_k"])
    req = build_request(cfg, args.query, top_k)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500] if e.fp else ""
        emit({"status": "request_error", "error": f"HTTP {e.code} {e.reason}", "body": detail}, 3)
    except (urllib.error.URLError, OSError) as e:
        emit({"status": "request_error", "error": str(e)}, 3)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        emit({"status": "parse_error", "error": f"response was not JSON: {e}", "raw": raw[:500]}, 3)

    try:
        results = parse_response(payload, cfg)
    except ValueError as e:
        emit({"status": "parse_error", "error": str(e), "raw": raw[:500]}, 3)

    emit({"status": "ok", "query": args.query, "top_k": top_k,
          "count": len(results), "results": results}, 0)


if __name__ == "__main__":
    main()
