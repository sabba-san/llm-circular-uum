#!/usr/bin/env bash
set -e

# If SQLite knowledge base database is missing (e.g. initial fresh volume mount), run ingestion
DB_FILE="/app/data/uum_knowledge.db"
if [ ! -f "$DB_FILE" ] && [ -f "data/uum_knowledge.db" ]; then
    DB_FILE="data/uum_knowledge.db"
fi

if [ ! -f "$DB_FILE" ]; then
    echo "[docker-entrypoint] Knowledge base database not found. Building knowledge base..."
    python3 ingest.py
fi

# Allow passing custom commands (e.g., docker run llm-uum streamlit run app.py)
if [ $# -gt 0 ]; then
    exec "$@"
else
    echo "[docker-entrypoint] Starting LLM UUM Web Server on port ${PORT:-8000}..."
    exec uvicorn web_app:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
fi
