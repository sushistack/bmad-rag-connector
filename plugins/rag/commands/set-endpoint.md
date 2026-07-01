---
description: Set (or clear) the RAG endpoint URL. Persists across sessions; used on the next /rag:rag-query.
argument-hint: <url>   (pass nothing to clear)
disable-model-invocation: true
---

Persist the RAG endpoint URL for this plugin. The value to set is: **$ARGUMENTS**

Run exactly this, then report the printed result. An empty `$ARGUMENTS` clears the override so config falls back to env vars / BMad TOML.

```bash
python3 - endpoint_url "$ARGUMENTS" <<'PY'
import json, os, sys
key, val = sys.argv[1], sys.argv[2]
base = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.expanduser("~/.config/rag-query")
os.makedirs(base, exist_ok=True)
p = os.path.join(base, "config-override.json")
d = json.load(open(p)) if os.path.exists(p) else {}
if val:
    d[key] = val
else:
    d.pop(key, None)
json.dump(d, open(p, "w"), indent=2)
os.chmod(p, 0o600)
print(json.dumps({"status": "ok", "key": key, "action": "set" if val else "cleared", "path": p}))
PY
```

Takes effect on the next `/rag:rag-query` call.
