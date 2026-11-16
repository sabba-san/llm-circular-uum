"""Baseline tests for PDF chunking and SQLite knowledge base metadata."""

import os
import sqlite3
from src.ingestion import chunk_document
from src.ai_provider import find_root_dir

ROOT_DIR = find_root_dir()
SQLITE_DB = os.path.join(ROOT_DIR, "data", "uum_knowledge.db")
SAMPLE_PDF = os.path.join(
    ROOT_DIR,
    "circular_forms",
    "College_documents",
    "cas",
    "02_academic_handbooks",
    "central_cas",
    "panduan_akademik_sesi_2015_2016_cas_extracted",
    "Panduan Akademik Sesi 2015_2016_CAS",
    "6.UUM CAS",
    "Maklumat Umum.pdf",
)


def test_chunk_document_pdf():
    """chunk_document() extracts non-empty page/heading/text chunks from a real PDF."""
    assert os.path.isfile(SAMPLE_PDF), f"Sample PDF missing: {SAMPLE_PDF}"
    chunks = chunk_document(SAMPLE_PDF)

    assert len(chunks) > 0
    for chk in chunks:
        assert isinstance(chk["page"], int) and chk["page"] >= 1
        assert isinstance(chk["heading"], str) and len(chk["heading"].strip()) > 0
        assert isinstance(chk["text"], str) and len(chk["text"].strip()) > 30


def test_sqlite_document_chunks_metadata():
    """Verify document_chunks schema and populated metadata in data/uum_knowledge.db."""
    assert os.path.isfile(SQLITE_DB), f"SQLite DB missing: {SQLITE_DB}"
    con = sqlite3.connect(SQLITE_DB)
    try:
        cols = {row[1] for row in con.execute("PRAGMA table_info(document_chunks)")}
        expected_cols = {
            "chunk_id",
            "circular_id",
            "department",
            "status",
            "section_heading",
            "page_number",
            "chunk_text",
            "doc_type",
            "academic_session",
        }
        assert expected_cols.issubset(cols)

        null_or_bad = con.execute(
            "SELECT count(*) FROM document_chunks "
            "WHERE chunk_id IS NULL OR chunk_text IS NULL OR trim(chunk_text) = '' "
            "OR page_number IS NULL OR page_number < 1"
        ).fetchone()[0]
        assert null_or_bad == 0

        statuses = {r[0] for r in con.execute("SELECT DISTINCT status FROM document_chunks")}
        assert "Active" in statuses

        college_sessions = con.execute(
            "SELECT count(*) FROM document_chunks WHERE doc_type = 'college_doc' AND academic_session IS NOT NULL AND trim(academic_session) != ''"
        ).fetchone()[0]
        assert college_sessions > 0
    finally:
        con.close()
