#!/usr/bin/env python3
"""
Database Setup & Schema Migration for UUM Circular Intelligence System
Supports:
- PostgreSQL + pgvector (Production & Cloud: Neon/Supabase)
- SQLite with FTS5 (Local Zero-Config Fallback)
"""

import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.ai_provider import load_env, find_root_dir

load_env()
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("DBSetup")

POSTGRES_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS circulars (
    id VARCHAR(50) PRIMARY KEY,
    ref_no VARCHAR(255) NOT NULL,
    title TEXT NOT NULL,
    department VARCHAR(100) NOT NULL,
    category VARCHAR(100),
    effective_date VARCHAR(50),
    year VARCHAR(10),
    status VARCHAR(20) DEFAULT 'Active',
    supersedes VARCHAR(255),
    required_forms TEXT,
    file_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS required_documents_forms (
    id VARCHAR(50) PRIMARY KEY,
    form_code VARCHAR(50) NOT NULL,
    form_title TEXT NOT NULL,
    department VARCHAR(100) NOT NULL,
    related_circular TEXT,
    project_activity_type VARCHAR(100) NOT NULL,
    is_mandatory VARCHAR(20) DEFAULT 'Mandatory',
    file_path TEXT NOT NULL,
    file_format VARCHAR(10),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS college_documents (
    id VARCHAR(50) PRIMARY KEY,
    title TEXT NOT NULL,
    college VARCHAR(100) NOT NULL,
    school VARCHAR(100),
    category VARCHAR(100),
    academic_level VARCHAR(50),
    academic_session VARCHAR(50),
    status VARCHAR(20) DEFAULT 'Active',
    file_format VARCHAR(20),
    file_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS college_forms (
    id VARCHAR(50) PRIMARY KEY,
    form_code VARCHAR(100) NOT NULL,
    form_title TEXT NOT NULL,
    college VARCHAR(100) NOT NULL,
    school VARCHAR(100),
    form_category VARCHAR(100),
    target_user VARCHAR(100),
    academic_session VARCHAR(50),
    file_format VARCHAR(20),
    file_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id VARCHAR(50) PRIMARY KEY,
    circular_id VARCHAR(50),
    circular_ref_no VARCHAR(255),
    department VARCHAR(100),
    status VARCHAR(20),
    section_heading TEXT,
    page_number INT,
    chunk_text TEXT NOT NULL,
    required_forms TEXT,
    doc_type VARCHAR(50) DEFAULT 'circular',
    college VARCHAR(100),
    school VARCHAR(100),
    academic_level VARCHAR(50),
    academic_session VARCHAR(50),
    target_user VARCHAR(100),
    embedding vector(768),
    tsv_content tsvector GENERATED ALWAYS AS (to_tsvector('simple', chunk_text || ' ' || COALESCE(section_heading, '') || ' ' || COALESCE(circular_ref_no, '') || ' ' || COALESCE(college, '') || ' ' || COALESCE(school, ''))) STORED
);

CREATE INDEX IF NOT EXISTS idx_chunks_vec ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON document_chunks USING gin (tsv_content);
CREATE INDEX IF NOT EXISTS idx_circ_status ON circulars (status);
CREATE INDEX IF NOT EXISTS idx_circ_dept ON circulars (department);
"""

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS circulars (
    id TEXT PRIMARY KEY,
    ref_no TEXT NOT NULL,
    title TEXT NOT NULL,
    department TEXT NOT NULL,
    category TEXT,
    effective_date TEXT,
    year TEXT,
    status TEXT DEFAULT 'Active',
    supersedes TEXT,
    required_forms TEXT,
    file_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS required_documents_forms (
    id TEXT PRIMARY KEY,
    form_code TEXT NOT NULL,
    form_title TEXT NOT NULL,
    department TEXT NOT NULL,
    related_circular TEXT,
    project_activity_type TEXT NOT NULL,
    is_mandatory TEXT DEFAULT 'Mandatory',
    file_path TEXT NOT NULL,
    file_format TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS college_documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    college TEXT NOT NULL,
    school TEXT,
    category TEXT,
    academic_level TEXT,
    academic_session TEXT,
    status TEXT DEFAULT 'Active',
    file_format TEXT,
    file_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS college_forms (
    id TEXT PRIMARY KEY,
    form_code TEXT NOT NULL,
    form_title TEXT NOT NULL,
    college TEXT NOT NULL,
    school TEXT,
    form_category TEXT,
    target_user TEXT,
    academic_session TEXT,
    file_format TEXT,
    file_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id TEXT PRIMARY KEY,
    circular_id TEXT,
    circular_ref_no TEXT,
    department TEXT,
    status TEXT,
    section_heading TEXT,
    page_number INTEGER,
    chunk_text TEXT NOT NULL,
    required_forms TEXT,
    doc_type TEXT DEFAULT 'circular',
    college TEXT,
    school TEXT,
    academic_level TEXT,
    academic_session TEXT,
    target_user TEXT,
    embedding_json TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    circular_ref_no,
    department,
    section_heading,
    chunk_text,
    college,
    school
);
"""

def ensure_schema_migrations(con, is_postgres=False):
    """Safely add college columns to document_chunks if they do not exist."""
    cols_to_add = [
        ("doc_type", "VARCHAR(50) DEFAULT 'circular'"),
        ("college", "VARCHAR(100)"),
        ("school", "VARCHAR(100)"),
        ("academic_level", "VARCHAR(50)"),
        ("academic_session", "VARCHAR(50)"),
        ("target_user", "VARCHAR(100)")
    ] if is_postgres else [
        ("doc_type", "TEXT DEFAULT 'circular'"),
        ("college", "TEXT"),
        ("school", "TEXT"),
        ("academic_level", "TEXT"),
        ("academic_session", "TEXT"),
        ("target_user", "TEXT")
    ]
    cur = con.cursor()
    if is_postgres:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'document_chunks';"
        )
        existing_cols = {row[0] for row in cur.fetchall()}
    else:
        cur.execute("PRAGMA table_info(document_chunks);")
        existing_cols = {row[1] for row in cur.fetchall()}

    for col_name, col_type in cols_to_add:
        if col_name not in existing_cols:
            cur.execute(f"ALTER TABLE document_chunks ADD COLUMN {col_name} {col_type};")

def setup_postgresql(db_url):
    """Setup PostgreSQL database tables and pgvector extension."""
    try:
        import psycopg2
        logger.info("Connecting to PostgreSQL...")
        con = psycopg2.connect(db_url)
        con.autocommit = True
        cur = con.cursor()
        cur.execute(POSTGRES_SCHEMA)
        ensure_schema_migrations(con, is_postgres=True)
        logger.info("✓ PostgreSQL schema initialized successfully with pgvector & FTS indexes!")
        cur.close()
        con.close()
        return True
    except Exception as e:
        logger.error(f"PostgreSQL connection/setup failed: {e}")
        return False

def setup_sqlite(sqlite_path=None):
    """Setup local SQLite database as fallback."""
    import sqlite3
    if sqlite_path is None:
        root_dir = find_root_dir()
        sqlite_path = os.path.join(root_dir, "data", "uum_knowledge.db")
    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    con = sqlite3.connect(sqlite_path, timeout=60.0)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA busy_timeout=60000;")
    cur = con.cursor()
    cur.executescript(SQLITE_SCHEMA)
    ensure_schema_migrations(con, is_postgres=False)
    con.commit()
    con.close()
    logger.info(f"✓ Local SQLite database initialized at: {sqlite_path}")
    return True


def rebuild_sqlite_fts(sqlite_con):
    """Rebuild the SQLite FTS5 virtual table with titles, forms, and academic sessions."""
    sqlite_con.execute("DROP TABLE IF EXISTS chunks_fts;")
    sqlite_con.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            chunk_id UNINDEXED,
            circular_ref_no,
            department,
            section_heading,
            chunk_text,
            college,
            school
        );
    """)
    sqlite_con.execute("""
        INSERT INTO chunks_fts (chunk_id, circular_ref_no, department, section_heading, chunk_text, college, school)
        SELECT d.chunk_id,
               COALESCE(d.circular_ref_no, '') || ' ' || COALESCE(c.title, cd.title, rf.form_title, cf.form_title, ''),
               d.department,
               d.section_heading,
               d.chunk_text || ' ' || COALESCE(d.required_forms, '') || ' ' || COALESCE(d.academic_session, ''),
               COALESCE(d.college, ''),
               COALESCE(d.school, '')
        FROM document_chunks d
        LEFT JOIN circulars c ON d.circular_id = c.id
        LEFT JOIN college_documents cd ON d.circular_id = cd.id
        LEFT JOIN required_documents_forms rf ON d.circular_id = rf.id
        LEFT JOIN college_forms cf ON d.circular_id = cf.id;
    """)
    sqlite_con.commit()


def get_sqlite_path():
    """Return the canonical path to the local SQLite knowledge base."""
    return os.path.join(find_root_dir(), "data", "uum_knowledge.db")


def get_kb_health_stats(sqlite_path=None):
    """Verify SQLite connectivity and return document and chunk counts."""
    import sqlite3

    db_path = sqlite_path or get_sqlite_path()
    if not os.path.exists(db_path):
        return {"ok": False, "database": "missing", "documents": {}, "chunks": 0}

    con = None
    try:
        con = sqlite3.connect(db_path, timeout=5.0)
        cur = con.cursor()
        cur.execute("SELECT 1;")
        cur.fetchone()

        def _count(query):
            try:
                return cur.execute(query).fetchone()[0]
            except sqlite3.OperationalError:
                return 0

        circulars = _count("SELECT count(*) FROM circulars;")
        active_circulars = _count("SELECT count(*) FROM circulars WHERE status = 'Active';")
        superseded_circulars = _count("SELECT count(*) FROM circulars WHERE status = 'Superseded';")
        admin_forms = _count("SELECT count(*) FROM required_documents_forms;")
        college_docs = _count("SELECT count(*) FROM college_documents;")
        college_forms = _count("SELECT count(*) FROM college_forms;")
        chunks = _count("SELECT count(*) FROM document_chunks;")

        return {
            "ok": chunks > 0,
            "database": "ok" if chunks > 0 else "empty",
            "documents": {
                "circulars": circulars,
                "active_circulars": active_circulars,
                "superseded_circulars": superseded_circulars,
                "admin_forms": admin_forms,
                "college_documents": college_docs,
                "college_forms": college_forms,
                "total": circulars + admin_forms + college_docs + college_forms,
            },
            "chunks": chunks,
        }
    except sqlite3.Error as exc:
        logger.warning(f"SQLite health check failed: {exc}")
        return {"ok": False, "database": "error", "detail": str(exc), "documents": {}, "chunks": 0}
    finally:
        if con is not None:
            con.close()


def load_catalog_tables(sqlite_path=None):
    """Load catalog tables as lists of dicts plus summary stats for UI dashboards."""
    import sqlite3

    db_path = sqlite_path or get_sqlite_path()
    if not os.path.exists(db_path):
        return [], [], [], [], {}

    con = sqlite3.connect(db_path, timeout=60.0)
    con.row_factory = sqlite3.Row
    try:
        def _fetch(query):
            try:
                return [dict(r) for r in con.execute(query).fetchall()]
            except sqlite3.OperationalError:
                return []

        circ_rows = _fetch("SELECT * FROM circulars ORDER BY department, status, year DESC;")
        form_rows = _fetch("SELECT * FROM required_documents_forms ORDER BY department, form_code;")
        college_doc_rows = _fetch("SELECT * FROM college_documents ORDER BY college, school, academic_session DESC;")
        college_form_rows = _fetch("SELECT * FROM college_forms ORDER BY college, school, form_code;")

        health = get_kb_health_stats(db_path)
        docs = health.get("documents", {})
        stats = {
            "total_circulars": len(circ_rows),
            "active_circulars": docs.get("active_circulars", 0),
            "superseded_circulars": docs.get("superseded_circulars", 0),
            "total_forms": len(form_rows),
            "total_college_docs": len(college_doc_rows),
            "total_college_forms": len(college_form_rows),
            "total_chunks": health.get("chunks", 0),
        }
        return circ_rows, form_rows, college_doc_rows, college_form_rows, stats
    finally:
        con.close()

def init_database():
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if db_url:
        print("[*] Detected DATABASE_URL. Initializing PostgreSQL...")
        if not setup_postgresql(db_url):
            print("[!] Falling back to local SQLite database...")
            setup_sqlite()
    else:
        setup_sqlite()

if __name__ == "__main__":
    init_database()

