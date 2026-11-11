#!/usr/bin/env python3
"""
LLM UUM — Academic & Circular Document Intelligence Web Server
Built with Starlette + Uvicorn, serving a 3-pane LLM UUM UI:
  1. Left Sidebar: Threads, My Saved Library, Master Catalog & Scope Filters
  2. Center Pane: AI Synthesis with Clickable Inline Citations & Form Chips
  3. Right Pane: LLM UUM Reference Cards & Live PDF / Document Inspector

Usage:
    ./venv/bin/uvicorn web_app:app --host 127.0.0.1 --port 8000 --reload
"""

import os
import sqlite3
import mimetypes
from urllib.parse import quote
from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse, HTMLResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from src.ai_provider import load_env, find_root_dir
from src.search import UUMAssistant

load_env()

ROOT_DIR = os.path.realpath(find_root_dir())
ALLOWED_DOCS_DIR = os.path.realpath(os.path.join(ROOT_DIR, "circular_forms"))
SQLITE_DB = os.path.join(ROOT_DIR, "data", "uum_knowledge.db")
TEMPLATE_PATH = os.path.join(ROOT_DIR, "templates", "index.html")
STATIC_DIR = os.path.join(ROOT_DIR, "static")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.dirname(TEMPLATE_PATH), exist_ok=True)

ALLOWED_SCOPES = {
    "All", "All UUM", "Circulars", "Colleges",
    "CAS", "COB", "COLGIS", "HEA",
    "RMC", "Bendahari", "ICC", "JUU",
}

_assistant = None


def get_assistant():
    global _assistant
    if _assistant is None:
        _assistant = UUMAssistant()
    return _assistant


async def homepage(request):
    """Serve the 3-pane LLM UUM SPA shell."""
    if not os.path.exists(TEMPLATE_PATH):
        return HTMLResponse("<h1>Template not found</h1>", status_code=500)
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }
    return HTMLResponse(html_content, headers=headers)


async def api_catalog(request):
    """Return knowledge base statistics and all cataloged documents & forms."""
    ast = get_assistant()
    items = list(ast.doc_registry.values())

    total_chunks = 0
    active_circulars = 0
    if os.path.exists(SQLITE_DB):
        con = sqlite3.connect(SQLITE_DB, timeout=60.0)
        try:
            cur = con.cursor()
            cur.execute("SELECT count(*) FROM document_chunks;")
            total_chunks = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM circulars WHERE status = 'Active';")
            active_circulars = cur.fetchone()[0]
        finally:
            con.close()

    stats = {
        "total_documents": len(items),
        "total_circulars": sum(1 for x in items if x.get("doc_type") == "circular"),
        "active_circulars": active_circulars,
        "total_admin_forms": sum(1 for x in items if x.get("doc_type") == "admin_form"),
        "total_college_docs": sum(1 for x in items if x.get("doc_type") == "college_doc"),
        "total_college_forms": sum(1 for x in items if x.get("doc_type") == "college_form"),
        "total_chunks": total_chunks,
        "ai_engine": "Google Gemini Flash" if os.environ.get("GEMINI_API_KEY") else "Groq / Extractive Engine",
    }
    return JSONResponse({"stats": stats, "items": items})


async def api_ask(request):
    """Execute hybrid RAG search + synthesis and return sources with document preview metadata."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON request body."}, status_code=400)

    query = str(body.get("query", "")).strip()
    if not query:
        return JSONResponse({"error": "Query cannot be empty."}, status_code=400)
    if len(query) > 1000:
        query = query[:1000]

    scope = str(body.get("scope", "All")).strip()
    if scope not in ALLOWED_SCOPES:
        scope = "All"

    filter_active = bool(body.get("filter_active", True))

    ast = get_assistant()
    res = ast.ask(query=query, filter_active=filter_active, scope=scope, top_k=6)
    return JSONResponse(res)


async def api_doc_preview(request):
    """Return metadata and extracted text sections for a specific document ID."""
    doc_id = request.path_params.get("doc_id", "").strip()
    if not doc_id or len(doc_id) > 120:
        return JSONResponse({"error": "Invalid document ID."}, status_code=400)

    ast = get_assistant()
    preview = ast.get_document_preview(doc_id)
    if not preview:
        return JSONResponse({"error": "Document not found in registry."}, status_code=404)

    return JSONResponse(preview)


async def api_serve_file(request):
    """Securely serve PDF, Image, or Word/Excel form by validated doc_id."""
    doc_id = request.path_params.get("doc_id", "").strip()
    is_download_route = request.url.path.endswith("/download")
    download = is_download_route or (request.query_params.get("download", "0") == "1")

    ast = get_assistant()
    meta = ast.doc_registry.get(doc_id)
    if not meta:
        for v in ast.doc_registry.values():
            if v.get("code") == doc_id or v.get("file_path") == doc_id:
                meta = v
                break

    if not meta:
        return JSONResponse({"error": "Document ID not found."}, status_code=404)

    rel_path = meta.get("file_path", "")
    if not rel_path:
        return JSONResponse({"error": "No file path associated with document."}, status_code=404)

    resolved_path = os.path.realpath(os.path.join(ROOT_DIR, rel_path))
    if not resolved_path.startswith(ALLOWED_DOCS_DIR + os.sep):
        return JSONResponse({"error": "Access denied outside document repository."}, status_code=403)

    if not os.path.isfile(resolved_path):
        return JSONResponse({"error": "File not found on disk."}, status_code=404)

    filename = os.path.basename(resolved_path)
    ext = os.path.splitext(filename)[1].lower()
    mime_type, _ = mimetypes.guess_type(resolved_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    # Office files & archives download as attachment; PDFs & images render inline unless ?download=1 or /download route
    is_inline_viewable = ext in (".pdf", ".png", ".jpg", ".jpeg") and not download
    disposition_type = "inline" if is_inline_viewable else "attachment"

    # Sanitize ASCII filename to avoid Starlette Latin-1 header encoding crash on Unicode characters (e.g. en-dash)
    ascii_fn = filename.encode("ascii", "ignore").decode("ascii").replace('"', "").strip()
    if not ascii_fn:
        ascii_fn = f"document{ext}"
    encoded_fn = quote(filename)

    headers = {
        "Content-Disposition": f"{disposition_type}; filename=\"{ascii_fn}\"; filename*=UTF-8''{encoded_fn}",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Accept-Ranges": "bytes",
    }
    return FileResponse(resolved_path, media_type=mime_type, headers=headers)


routes = [
    Route("/", endpoint=homepage, methods=["GET"]),
    Route("/api/catalog", endpoint=api_catalog, methods=["GET"]),
    Route("/api/ask", endpoint=api_ask, methods=["POST"]),
    Route("/api/doc/{doc_id}", endpoint=api_doc_preview, methods=["GET"]),
    Route("/api/file/{doc_id}", endpoint=api_serve_file, methods=["GET"]),
    Route("/api/document/{doc_id}/preview", endpoint=api_serve_file, methods=["GET"]),
    Route("/api/document/{doc_id}/download", endpoint=api_serve_file, methods=["GET"]),
    Mount("/static", app=StaticFiles(directory=STATIC_DIR), name="static"),
]

app = Starlette(debug=False, routes=routes)

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("web_app:app", host=host, port=port, reload=True)

