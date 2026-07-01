---
description: Set (or clear) the RAG API token/key. Persists across sessions (stored chmod 600).
argument-hint: <token>   (pass nothing to clear)
disable-model-invocation: true
---

Persist the RAG credential for this plugin.

⚠️ Security: the token you typed is now in this conversation's transcript (stored under `~/.claude/projects/...`). This slash command exists for environments where the plugin's masked config prompt isn't available. When you can, prefer the plugin config prompt (keychain, masked) or the `RAG_CREDENTIAL` environment variable instead.

Run exactly this, then report the result **without echoing the token value**. An empty `$ARGUMENTS` clears it.

```bash
python3 - credential "$ARGUMENTS" <<'PY'
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

Takes effect on the next `/rag:query` call. The file is written `chmod 600` (owner-only) and lives outside the repo.
