"""Baseline Starlette TestClient tests for web_app.py API and file serving routes."""

from starlette.testclient import TestClient
import web_app


def _disable_llm_keys(monkeypatch):
    """Ensure /api/ask uses Offline Extractive Engine during tests."""
    for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    ast = web_app.get_assistant()
    ast.ai.gemini_key = ""
    ast.ai.groq_key = ""
    ast.ai.openrouter_key = ""


def test_health_endpoint():
    client = TestClient(web_app.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["documents"]["total"] > 0
    assert data["chunks"] > 0


def test_health_endpoint_rejects_empty_chunks(monkeypatch, tmp_path):
    """If a mounted DB has 0 chunks (e.g. broken WSL2 mount), /health must return 503."""
    import sqlite3
    empty_db = tmp_path / "empty.db"
    con = sqlite3.connect(str(empty_db))
    con.execute("CREATE TABLE document_chunks (chunk_id TEXT);")
    con.commit()
    con.close()

    monkeypatch.setattr(web_app, "SQLITE_DB", str(empty_db))
    client = TestClient(web_app.app)
    resp = client.get("/health")
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "error"
    assert data["database"] == "empty"
    assert data["chunks"] == 0


def test_catalog_endpoint():
    client = TestClient(web_app.app)
    resp = client.get("/api/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert "stats" in data and "items" in data
    assert data["stats"]["total_documents"] > 0
    assert len(data["items"]) > 0


def test_ask_endpoint_offline(monkeypatch):
    _disable_llm_keys(monkeypatch)
    client = TestClient(web_app.app)
    resp = client.post("/api/ask", json={"query": "RMC 008", "scope": "All"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "Offline Extractive Engine"
    assert len(data["sources"]) > 0
    assert len(data["answer"]) > 0
    assert 1 <= len(data.get("follow_up_questions", [])) <= 3


def test_document_preview_and_file_spaces_and_unicode():
    """Verify /api/document/{id}/preview and /api/file/{id} handle spaces and Unicode filenames."""
    client = TestClient(web_app.app)

    # 1. Bahasa Melayu filename with spaces (CDOC-CAS-001 -> Maklumat Umum.pdf)
    for url in ("/api/document/CDOC-CAS-001/preview", "/api/file/CDOC-CAS-001"):
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "inline;" in resp.headers["content-disposition"]
        assert "Maklumat%20Umum.pdf" in resp.headers["content-disposition"]

    # 2. Any document in registry with non-ASCII Unicode characters in filename (e.g. en-dash)
    ast = web_app.get_assistant()
    unicode_doc_id = next(
        (
            doc_id
            for doc_id, meta in ast.doc_registry.items()
            if any(ord(ch) > 127 for ch in (meta.get("file_path") or ""))
        ),
        None,
    )
    if unicode_doc_id:
        resp = client.get(f"/api/document/{unicode_doc_id}/preview")
        assert resp.status_code == 200
        assert "filename*=UTF-8''" in resp.headers["content-disposition"]
