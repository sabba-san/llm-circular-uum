# TODO: PDF Viewer Troubleshooting & Enhancements (Abbas)

**Date**: 2026-11-10 (Updated: 2026-11-11)  
**Author**: Ahmad Abbas  
**Status**: ✅ Resolved & Dockerized  

---

## Issue Resolution Summary

### 1. Root Causes Identified & Fixed
1. **Endpoint Route Mismatch**:
   - `static/app.js` was requesting `/api/document/{doc_id}/preview` and `/api/document/{doc_id}/download`, but `web_app.py` only had `/api/file/{doc_id}` mapped.
   - **Fix**: Added explicit `/api/document/{doc_id}/preview` and `/api/document/{doc_id}/download` routes in `web_app.py`, with code/path fallback resolution.
2. **Hidden Iframe Initialization Failure**:
   - Post-search auto-preview mounted an `<iframe>` inside a hidden `#panelViewer` (`display: none`), causing PDF plugins in Chrome/Firefox to compute a 0x0 viewport.
   - **Fix**: Refactored `openDocumentInInspector` and `switchRightTab` in `static/app.js` so viewer content is cleanly rendered while the panel is visible.
3. **Non-Latin-1 Filenames Crash**:
   - Documents with Unicode characters (such as en-dashes `–` in `CDOC-CLG-014` and `CDOC-CLG-015`) crashed Starlette's Latin-1 header serializer with `UnicodeEncodeError`.
   - **Fix**: Sanitized the ASCII fallback parameter in `Content-Disposition` while using RFC 5987 `filename*=UTF-8''` for unicode names.
4. **Enhanced Viewer Actions & Citation Page Jumping**:
   - Added **Open in New Tab** and **Download** action buttons to the Document Viewer toolbar.
   - Wired citation pill clicks to open exact cited pages directly (`#page=N`).
   - Added dynamic extraction fetching for Office forms (.docx/.xlsx) that lack pre-extracted chunk text.

---

## Docker Deployment

The application is fully containerized:
- **`Dockerfile`**: Minimal `python:3.12-slim` image with `poppler-utils` (`pdftotext`, `pdfimages`, `pdftoppm`), `tesseract-ocr`, and `curl`.
- **`docker-compose.yml`**: 1-click startup with persistent `./data` and `./circular_forms` mounts on port 8000.
- **`docker-entrypoint.sh`**: Auto-verifies SQLite knowledge base before launching `uvicorn web_app:app`.

### Quick Run Commands:
```bash
# Build and run with Docker Compose
docker compose up -d --build

# Or run with Docker CLI directly
docker build -t llm-uum .
docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/app/data llm-uum
```
