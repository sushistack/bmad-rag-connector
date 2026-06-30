#!/usr/bin/env python3
"""Self-check for rag_query's non-trivial logic: dotted-path dig, response parsing, auth headers.
Run: uv run tests/test_rag_query.py  (no network, no framework)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rag_query as rq


def test_dig():
    obj = {"a": {"b": {"c": 1}}, "x": [1, 2]}
    assert rq.dig(obj, "a.b.c") == 1
    assert rq.dig(obj, "a.b.missing") is None
    assert rq.dig(obj, "x.0") is None  # lists not indexed by dotted path
    assert rq.dig({"r": [1]}, "r") == [1]


def test_parse_response_default_and_nested():
    cfg = {"results_path": "results", "result_fields": {"text": "text", "source": "source", "score": "score"}}
    payload = {"results": [{"text": "hi", "source": "doc1", "score": 0.9}]}
    assert rq.parse_response(payload, cfg) == [{"text": "hi", "source": "doc1", "score": 0.9}]

    # config-driven remap: nested path + renamed array, zero code change
    cfg2 = {"results_path": "data.hits", "result_fields": {"text": "content", "source": "meta.url"}}
    payload2 = {"data": {"hits": [{"content": "body", "meta": {"url": "http://x"}}]}}
    assert rq.parse_response(payload2, cfg2) == [{"text": "body", "source": "http://x"}]


def test_parse_response_bad_path_raises():
    try:
        rq.parse_response({"results": {"not": "a list"}}, {"results_path": "results", "result_fields": {}})
    except ValueError as e:
        assert "results_path" in str(e)
    else:
        raise AssertionError("expected ValueError on non-list results_path")


def test_auth_headers():
    base = {"endpoint_url": "http://e", "credential": "SEKRET"}
    assert rq.build_request({**base, "auth_type": "bearer"}, "q", 5).headers["Authorization"] == "Bearer SEKRET"
    r = rq.build_request({**base, "auth_type": "custom_header", "auth_header_name": "X-Api-Key"}, "q", 5)
    assert r.headers["X-api-key"] == "SEKRET"  # urllib title-cases header keys
    none = rq.build_request({"endpoint_url": "http://e", "auth_type": "none"}, "q", 5)
    assert "Authorization" not in none.headers


def test_body_assembly():
    cfg = {"endpoint_url": "http://e", "auth_type": "none", "query_field": "q",
           "extra_body": {"index": "docs"}}
    req = rq.build_request(cfg, "hello", 3)
    body = json.loads(req.data)
    assert body == {"index": "docs", "q": "hello", "top_k": 3}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
    print("all passed")
