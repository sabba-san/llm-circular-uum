#!/usr/bin/env bash
set -e

# If SQLite knowledge base database is missing (e.g. initial fresh volume mount), run ingestion
DB_FILE="/app/data/uum_knowledge.db"
if [ ! -f "$DB_FILE" ] && [ -f "data/uum_knowledge.db" ]; then
    DB_FILE="data/uum_knowledge.db"
fi

# Check if database is missing, has 0 chunks, or needs schema/college documents upgrade
NEED_INGEST=0
if [ ! -f "$DB_FILE" ]; then
    echo "[docker-entrypoint] Knowledge base database not found. Building knowledge base..."
    NEED_INGEST=1
else
    # Check if college_documents table exists and document_chunks has indexed rows
    HAS_COLLEGE=$(python3 -c "import sqlite3; con=sqlite3.connect('$DB_FILE'); cur=con.cursor(); print(cur.execute(\"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='college_documents';\").fetchone()[0]); con.close()" 2>/dev/null || echo 0)
    CHUNK_COUNT=$(python3 -c "import sqlite3; con=sqlite3.connect('$DB_FILE'); cur=con.cursor(); print(cur.execute(\"SELECT count(*) FROM document_chunks;\").fetchone()[0]); con.close()" 2>/dev/null || echo 0)
    if [ "$HAS_COLLEGE" = "0" ] || [ "$CHUNK_COUNT" = "0" ]; then
        echo "[docker-entrypoint] Existing database is incomplete (chunks=$CHUNK_COUNT, college_table=$HAS_COLLEGE). Rebuilding knowledge base..."
        NEED_INGEST=1
    fi
fi

if [ "$NEED_INGEST" = "1" ]; then
    DOCS_DIR="/app/circular_forms"
    if [ ! -d "$DOCS_DIR" ] && [ -d "circular_forms" ]; then
        DOCS_DIR="circular_forms"
    fi
    if [ ! -d "$DOCS_DIR" ] || [ -z "$(ls -A "$DOCS_DIR" 2>/dev/null)" ]; then
        echo "[docker-entrypoint] ERROR: '$DOCS_DIR' is empty or not mounted (WSL2 bind-mount race)." >&2
        echo "[docker-entrypoint] Please run 'docker compose down && docker compose up -d' from your WSL2 terminal." >&2
        exit 1
    fi
    python3 ingest.py
fi

# Allow passing custom commands (e.g., docker run llm-uum streamlit run app.py)
if [ $# -gt 0 ]; then
    exec "$@"
else
    echo "[docker-entrypoint] Starting LLM UUM Web Server on port ${PORT:-8000}..."
    exec uvicorn web_app:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
fi
