#!/usr/bin/env bash
set -e

# If SQLite knowledge base database is missing (e.g. initial fresh volume mount), run ingestion
DB_FILE="/app/data/uum_knowledge.db"
if [ ! -f "$DB_FILE" ] && [ -f "data/uum_knowledge.db" ]; then
    DB_FILE="data/uum_knowledge.db"
fi

# Check if database is missing or needs schema/college documents upgrade
NEED_INGEST=0
if [ ! -f "$DB_FILE" ]; then
    echo "[docker-entrypoint] Knowledge base database not found. Building knowledge base..."
    NEED_INGEST=1
else
    # Check if college_documents table exists and is populated
    HAS_COLLEGE=$(python3 -c "import sqlite3; con=sqlite3.connect('$DB_FILE'); cur=con.cursor(); print(cur.execute(\"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='college_documents';\").fetchone()[0]); con.close()" 2>/dev/null || echo 0)
    if [ "$HAS_COLLEGE" = "0" ]; then
        echo "[docker-entrypoint] Existing database found, but missing college documents. Upgrading knowledge base..."
        NEED_INGEST=1
    fi
fi

if [ "$NEED_INGEST" = "1" ]; then
    python3 ingest.py
fi

# Allow passing custom commands (e.g., docker run llm-uum streamlit run app.py)
if [ $# -gt 0 ]; then
    exec "$@"
else
    echo "[docker-entrypoint] Starting LLM UUM Web Server on port ${PORT:-8000}..."
    exec uvicorn web_app:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
fi
