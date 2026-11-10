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
    for col_name, col_type in cols_to_add:
        try:
            cur.execute(f"ALTER TABLE document_chunks ADD COLUMN {col_name} {col_type};")
        except Exception:
            pass  # column already exists

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

