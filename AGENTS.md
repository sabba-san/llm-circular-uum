# AGENTS.md

1. **Read [`FEATURE_MAP.md`](./FEATURE_MAP.md) first** to locate files, endpoints, and handlers without broad repo searches.
2. **Architectural boundaries**:
   - Web/UI layers (`web_app.py`, `app.py`) must not import `sqlite3` or `psycopg2` directly; put database queries in `src/db.py` or `src/search.py`.
   - Core modules in `src/` must remain UI-agnostic (never import `starlette`, `uvicorn`, or `streamlit`).
3. **No workarounds or excuse comments**:
   - Never add `except Exception: pass`, mutate `sys.argv`, call `subprocess.run()` without `timeout=`, or write comment excuses for hacks—fix the root cause.
4. **Verify before finishing**:
   - Run `./scripts/verify` after any code change (and `./scripts/verify --eval` when modifying `src/search.py` or ingestion).
