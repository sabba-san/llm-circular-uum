# Feature Map (`llm_uum`)

Compact index of user-facing views, HTTP routes, webhooks, CLIs, and core modules.

## 1. Primary 3-Pane Web App (Starlette + Uvicorn, Port `8000`)
- **Server Entry**: `web_app.py` (`app = Starlette(...)`)
- **HTML Shell & Assets**: `templates/index.html`, `static/app.js`, `static/styles.css`
- **Frontend Views & Handlers (`static/app.js`)**:
  - **Search & Synthesis (`#viewSearch`)**: `triggerSearch()`, `renderAssistantTurn()`, `renderLLMUUMMarkdown()`, `renderLinkedFormsChips()`
  - **Follow-Up Question Pills (`.followup-section`)**: `renderFollowUpQuestions()`
  - **Query Auto-Predict (`#autoPredictMenu`)**: `buildAutoPredictSuggestions()`, `updateAutoPredict()`, `renderAutoPredict()`
  - **Recents Thread Cache (`#threadsList`)**: `saveThreadHistory()`, `restoreSavedThread()`, `renderThreadHistory()` (`localStorage["uum_threads"]`)
  - **Master Document Library (`#viewCatalog`)**: `loadCatalog()`, `renderCatalogItems()`
  - **My Saved Library (`#viewSaved`)**: `toggleSaveItem()`, `renderSavedList()` (`localStorage["uum_saved_items"]`)
  - **Right Pane — References & Live PDF/Document Inspector (`#rightPane`)**: `renderReferenceCards()`, `openDocumentInInspector()`, `switchRightTab()`

## 2. HTTP API Endpoints (`web_app.py`)
| Route | Handler | Backing Service / Data |
| :--- | :--- | :--- |
| `GET /` | `homepage` | Serves `templates/index.html` |
| `GET /health` | `health_check` | SQLite connectivity + table counts (`503` if missing or `chunks == 0`) |
| `GET /api/catalog` | `api_catalog` | `UUMAssistant.doc_registry` + live DB stats |
| `POST /api/ask` | `api_ask` | `UUMAssistant.ask(query, filter_active, scope, top_k, previous_query)` |
| `GET /api/doc/{doc_id}` | `api_doc_preview` | `UUMAssistant.get_document_preview(doc_id)` |
| `GET /api/file/{doc_id}` | `api_serve_file` | Path-jailed (`ALLOWED_DOCS_DIR`) file serving + RFC 5987 UTF-8 header |
| `GET /api/document/{doc_id}/preview` | `api_serve_file` | Inline PDF/image preview (`Content-Disposition: inline`) |
| `GET /api/document/{doc_id}/download` | `api_serve_file` | Attachment download (`Content-Disposition: attachment`) |

## 3. Secondary Interfaces & Webhooks
- **Admin Streamlit Dashboard (Port `8501`)**: `app.py` (Catalog explorer, Excel download, supervisor demo scenarios, in-app `pipeline.py` trigger)
- **n8n Automation Webhook (Port `5678`)**: `n8n/llm_uum_chat_webhook_workflow.json` (`POST /webhook/uum-chat` → `http://llm-uum:8000/api/ask`), guide in `docs/N8N_WORKFLOW_GUIDE.md`

## 4. CLI Entrypoints & Evaluation
- `pipeline.py`: Unified 1-click sync (`--all`, `--circulars-only`, `--college-only`, `--clean`, `--force-ocr`, `--force-reembed`)
- `ingest.py`: Chunking & vector indexing CLI (`--circulars-only`, `--college-only`, `--force-reembed`)
- `sort.py`: PTJ circular/form metadata & OCR scanner (`src.tracker_sorter.main`)
- `ask.py`: CLI Q&A assistant (one-shot & `-i` interactive mode)
- `eval/run_ir_eval.py`: Phase 5 IR benchmark (`P@K`, `R@K`, `MRR@K`, `nDCG@K`, weight ablation) against `eval/bilingual_eval_set.json` -> `eval/baseline_results.json`
- `scripts/verify`: Unified verification CLI (`--eval`, `--ui-fuzz`, `--ui-fuzz-offline`, `--verbose`)

## 5. Core Domain Package (`src/`)
- `src/search.py`: `UUMAssistant` (40:60 hybrid BM25 + vector search, `expand_query_tokens`, `QUERY_STOPWORDS`, `_extract_reference_codes`, `_generate_follow_up_questions`, `_ensure_fresh_sqlite`)
- `src/ai_provider.py`: `AIProvider` (Gemini Flash primary → Groq Llama 3.3 → OpenRouter → Tier 4 Offline Extractive Engine; `get_embedding`, `batch_get_embeddings`, `find_root_dir`, `load_env`)
- `src/db.py`: Dual-mode DB schema & helpers (`setup_sqlite`, `setup_postgresql`, `rebuild_sqlite_fts`)
- `src/ingestion.py`: PTJ circulars (`CIRC-*`, `CIRC-JUU-*`) & admin forms (`FORM-*`) chunker and embedder (`circular_Forms_tracker.xlsx`)
- `src/college_ingestion.py`: College handbooks (`CDOC-*`) & college forms (`CFORM-*`) chunker and embedder (`college_documents_tracker.xlsx`)
- `src/college_extractor.py`: Multi-format text & OCR extractor (`extract_document_chunks`)
- `src/tracker_sorter.py`: PTJ folder scanner, metadata/OCR parser, and `ExcelWriter`
- `src/college_tracker.py` & `src/college_organizer.py`: College folder organizer and tracker generator

## 6. Data, Config & Tests
- `data/uum_knowledge.db`: Local SQLite FTS5 + vector knowledge base (also supports `DATABASE_URL` PostgreSQL + `pgvector`)
- `tests/`: `pytest` suite (`test_search.py`, `test_ingestion.py`, `test_web_app.py`) and Bombadil property-based UI specification (`tests/bombadil/llm_uum.spec.ts`)
- `docker-compose.yml`, `Dockerfile`, `docker-entrypoint.sh`: Containerized `llm-uum` (`:8000`) and `n8n` (`:5678`) stack
- `pyproject.toml`, `requirements-dev.txt`, `package.json`: Linter (`ruff`), type-checker (`mypy`), dev/test dependencies, and `@antithesishq/bombadil`
