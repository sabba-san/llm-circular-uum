#!/usr/bin/env python3
"""
UUM College Documents Ingestion & Embedding Pipeline
Ingests:
1. Academic documents metadata from college_documents_tracker.xlsx ('college_docs') into 'college_documents' table
2. College forms metadata from college_documents_tracker.xlsx ('college_forms') into 'college_forms' table
3. Chunks documents (PDF, DOCX, DOC, Images/OCR, ZIP) and generates 768-d embeddings into 'document_chunks' table
4. Rebuilds SQLite FTS5 index for fast BM25 full-text search across all documents
"""

import os
import re
import sys
import time
import json
import sqlite3
import zipfile
import logging
import argparse
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.ai_provider import AIProvider, load_env, find_root_dir
from src.db import setup_sqlite, setup_postgresql
from src.college_extractor import extract_document_chunks

load_env()
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("CollegeIngestion")

ROOT_DIR = find_root_dir()
EXCEL_FILE = os.path.join(ROOT_DIR, "college_documents_tracker.xlsx")
SQLITE_DB = os.path.join(ROOT_DIR, "data", "uum_knowledge.db")

def determine_status(session_str):
    """Classify document status into Active (>=2024 or Current) or Historical (<2024)."""
    if not session_str or session_str.lower() in ("current", "active"):
        return "Active"
    m = re.search(r"20(\d{2})", session_str)
    if m:
        yr = int("20" + m.group(1))
        return "Active" if yr >= 2024 else "Historical"
    return "Active"

def read_sheet(excel_path, sheet_name):
    """Read rows from a specific sheet in an Excel .xlsx file."""
    with zipfile.ZipFile(excel_path, "r") as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheet_target = None
        for s in wb.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"):
            if s.attrib["name"] == sheet_name:
                r_id = s.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
                for rel in rels.iter("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
                    if rel.attrib["Id"] == r_id:
                        sheet_target = "xl/" + rel.attrib["Target"]
                        break
                break

        if not sheet_target:
            return []

        shared_strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in sst.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                shared_strings.append("".join(n.text for n in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t") if n.text))

        sheet = ET.fromstring(z.read(sheet_target))
        rows = []
        for row in sheet.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
            r_vals = []
            for c in row.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                val = v.text if v is not None else ""
                if c.attrib.get("t") == "s" and val.isdigit():
                    val = shared_strings[int(val)]
                r_vals.append(val)
            rows.append(r_vals)
        return rows

def load_tracker_data(excel_path):
    """Load both college_docs and college_forms from tracker."""
    doc_rows = read_sheet(excel_path, "college_docs")
    form_rows = read_sheet(excel_path, "college_forms")

    docs = []
    for r in doc_rows[1:]:
        if len(r) >= 10:
            session_str = r[6]
            docs.append({
                "id": r[0],
                "title": r[1],
                "college": r[2],
                "school": r[3],
                "category": r[4],
                "academic_level": r[5],
                "academic_session": session_str,
                "status": determine_status(session_str),
                "file_format": r[8],
                "file_path": r[9].replace("\\", "/"),
            })

    forms = []
    for r in form_rows[1:]:
        if len(r) >= 10:
            session_str = r[7]
            forms.append({
                "id": r[0],
                "form_code": r[1],
                "form_title": r[2],
                "college": r[3],
                "school": r[4],
                "form_category": r[5],
                "target_user": r[6],
                "academic_session": session_str,
                "status": determine_status(session_str),
                "file_format": r[8],
                "file_path": r[9].replace("\\", "/"),
            })

    return docs, forms

def run_college_ingestion(force_reembed=False):
    ai = AIProvider()
    docs, forms = load_tracker_data(EXCEL_FILE)
    logger.info(f"Loaded {len(docs)} college docs and {len(forms)} college forms from {EXCEL_FILE}")

    db_url = os.environ.get("DATABASE_URL", "").strip()
    use_postgres = bool(db_url)
    pg_con = None
    sqlite_con = None

    if use_postgres:
        try:
            import psycopg2
            pg_con = psycopg2.connect(db_url)
            pg_con.autocommit = True
            logger.info("Connected to PostgreSQL for college ingestion.")
        except Exception as e:
            logger.warning(f"Failed to connect to PostgreSQL ({e}). Using SQLite.")
            use_postgres = False

    if not use_postgres:
        setup_sqlite(SQLITE_DB)
        sqlite_con = sqlite3.connect(SQLITE_DB, timeout=60.0)
        sqlite_con.execute("PRAGMA busy_timeout = 60000;")
        logger.info(f"Using SQLite database: {SQLITE_DB}")

    # 1. Ingest College Documents Metadata
    print("\n[*] Ingesting college documents metadata...")
    for d in docs:
        if use_postgres:
            with pg_con.cursor() as cur:
                cur.execute("""
                    INSERT INTO college_documents (id, title, college, school, category, academic_level, academic_session, status, file_format, file_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title, college = EXCLUDED.college, school = EXCLUDED.school, category = EXCLUDED.category,
                        academic_level = EXCLUDED.academic_level, academic_session = EXCLUDED.academic_session, status = EXCLUDED.status,
                        file_format = EXCLUDED.file_format, file_path = EXCLUDED.file_path;
                """, (d["id"], d["title"], d["college"], d["school"], d["category"], d["academic_level"], d["academic_session"], d["status"], d["file_format"], d["file_path"]))
        else:
            sqlite_con.execute("""
                INSERT OR REPLACE INTO college_documents (id, title, college, school, category, academic_level, academic_session, status, file_format, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (d["id"], d["title"], d["college"], d["school"], d["category"], d["academic_level"], d["academic_session"], d["status"], d["file_format"], d["file_path"]))

    # 2. Ingest College Forms Metadata
    print("[*] Ingesting college forms metadata...")
    for f in forms:
        if use_postgres:
            with pg_con.cursor() as cur:
                cur.execute("""
                    INSERT INTO college_forms (id, form_code, form_title, college, school, form_category, target_user, academic_session, file_format, file_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        form_code = EXCLUDED.form_code, form_title = EXCLUDED.form_title, college = EXCLUDED.college,
                        school = EXCLUDED.school, form_category = EXCLUDED.form_category, target_user = EXCLUDED.target_user,
                        academic_session = EXCLUDED.academic_session, file_format = EXCLUDED.file_format, file_path = EXCLUDED.file_path;
                """, (f["id"], f["form_code"], f["form_title"], f["college"], f["school"], f["form_category"], f["target_user"], f["academic_session"], f["file_format"], f["file_path"]))
        else:
            sqlite_con.execute("""
                INSERT OR REPLACE INTO college_forms (id, form_code, form_title, college, school, form_category, target_user, academic_session, file_format, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f["id"], f["form_code"], f["form_title"], f["college"], f["school"], f["form_category"], f["target_user"], f["academic_session"], f["file_format"], f["file_path"]))

    # 3. Extract and Prepare Semantic Chunks
    print("[*] Parsing multi-format college documents into semantic chunks...")
    chunks_to_insert = []

    # Process Academic Documents
    for d_idx, d in enumerate(docs, 1):
        if d_idx % 40 == 0 or d_idx == len(docs):
            print(f"  [+] Parsed {d_idx}/{len(docs)} academic documents...")
        full_path = os.path.join(ROOT_DIR, d["file_path"])
        if not os.path.exists(full_path):
            continue

        raw_chunks = extract_document_chunks(full_path)
        for idx, chk in enumerate(raw_chunks, 1):
            chunk_id = f"CHK-{d['id']}-{idx:03d}"
            heading = chk["heading"]
            page = chk["page"]
            text = chk["text"]

            embed_input = f"[{d['college']} | {d['school']} | {d['academic_level']} | Session: {d['academic_session']}] {d['title']} (p.{page}) - {heading}\n{text}"
            chunks_to_insert.append({
                "chunk_id": chunk_id,
                "circular_id": d["id"],
                "circular_ref_no": d["title"],
                "department": f"{d['college']} — {d['school']}",
                "status": d["status"],
                "section_heading": heading,
                "page_number": page,
                "chunk_text": text,
                "required_forms": "-",
                "doc_type": "college_doc",
                "college": d["college"],
                "school": d["school"],
                "academic_level": d["academic_level"],
                "academic_session": d["academic_session"],
                "target_user": d["academic_level"],
                "embed_input": embed_input
            })

    # Process College Forms
    for f_idx, f in enumerate(forms, 1):
        if f_idx % 40 == 0 or f_idx == len(forms):
            print(f"  [+] Parsed {f_idx}/{len(forms)} college forms...")
        full_path = os.path.join(ROOT_DIR, f["file_path"])
        if not os.path.exists(full_path):
            continue

        raw_chunks = extract_document_chunks(full_path)
        for idx, chk in enumerate(raw_chunks, 1):
            chunk_id = f"CHK-{f['id']}-{idx:03d}"
            heading = chk["heading"]
            page = chk["page"]
            text = chk["text"]

            embed_input = f"[{f['college']} | {f['school']} | Form: {f['form_code']}] {f['form_title']} (Target: {f['target_user']}) - {heading}\n{text}"
            chunks_to_insert.append({
                "chunk_id": chunk_id,
                "circular_id": f["id"],
                "circular_ref_no": f"{f['form_code']} ({f['form_title']})",
                "department": f"{f['college']} — {f['school']}",
                "status": f["status"],
                "section_heading": heading,
                "page_number": page,
                "chunk_text": text,
                "required_forms": f"{f['form_code']} - {f['form_title']}",
                "doc_type": "college_form",
                "college": f["college"],
                "school": f["school"],
                "academic_level": "All Levels",
                "academic_session": f["academic_session"],
                "target_user": f["target_user"],
                "embed_input": embed_input
            })

    total_chunks = len(chunks_to_insert)
    print(f"[*] Generated {total_chunks} semantic chunks across all college documents.")

    # 4. Incremental Embedding Generation
    existing_embeddings = {}
    if not force_reembed:
        if use_postgres:
            with pg_con.cursor() as cur:
                cur.execute("SELECT chunk_id, embedding FROM document_chunks WHERE embedding IS NOT NULL;")
                for row in cur.fetchall():
                    existing_embeddings[row[0]] = row[1]
        else:
            cur = sqlite_con.cursor()
            cur.execute("SELECT chunk_id, embedding_json FROM document_chunks WHERE length(embedding_json) > 100;")
            for row in cur.fetchall():
                try:
                    existing_embeddings[row[0]] = json.loads(row[1])
                except Exception:
                    pass

    new_chunks = [ch for ch in chunks_to_insert if ch["chunk_id"] not in existing_embeddings]
    if new_chunks:
        print(f"[*] Found {len(new_chunks)} new/unembedded chunks out of {total_chunks} total college chunks. Generating embeddings...")
        batch_size = 50
        delay = 4.0
        total_batches = (len(new_chunks) + batch_size - 1) // batch_size
        for b_idx in range(total_batches):
            start = b_idx * batch_size
            batch = new_chunks[start:start + batch_size]
            batch_texts = [ch["embed_input"] for ch in batch]
            batch_embs = ai.batch_get_embeddings(batch_texts, batch_size=batch_size, delay=0)
            for idx, ch in enumerate(batch):
                emb = batch_embs[idx] if idx < len(batch_embs) else [0.0] * 768
                existing_embeddings[ch["chunk_id"]] = emb
                # Incremental persistence per batch
                if use_postgres:
                    with pg_con.cursor() as cur:
                        cur.execute("""
                            INSERT INTO document_chunks (chunk_id, circular_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms, doc_type, college, school, academic_level, academic_session, target_user, embedding)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (chunk_id) DO UPDATE SET
                                chunk_text = EXCLUDED.chunk_text, required_forms = EXCLUDED.required_forms, embedding = EXCLUDED.embedding;
                        """, (ch["chunk_id"], ch["circular_id"], ch["circular_ref_no"], ch["department"], ch["status"], ch["section_heading"], ch["page_number"], ch["chunk_text"], ch["required_forms"], ch["doc_type"], ch["college"], ch["school"], ch["academic_level"], ch["academic_session"], ch["target_user"], emb))
                else:
                    sqlite_con.execute("""
                        INSERT OR REPLACE INTO document_chunks (chunk_id, circular_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms, doc_type, college, school, academic_level, academic_session, target_user, embedding_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (ch["chunk_id"], ch["circular_id"], ch["circular_ref_no"], ch["department"], ch["status"], ch["section_heading"], ch["page_number"], ch["chunk_text"], ch["required_forms"], ch["doc_type"], ch["college"], ch["school"], ch["academic_level"], ch["academic_session"], ch["target_user"], json.dumps(emb)))

            if sqlite_con:
                sqlite_con.commit()

            print(f"  [+] Embedded and persisted {min(start + batch_size, len(new_chunks))}/{len(new_chunks)} chunks")
            if b_idx + 1 < total_batches and delay > 0:
                time.sleep(delay)
    else:
        print(f"[*] All {total_chunks} college chunks already have valid embeddings. (Incremental skip)")

    # 5. Store / sync any remaining chunks in Database
    print(f"[*] Ensuring all {total_chunks} college chunks are synchronized...")
    for ch in chunks_to_insert:
        embedding = existing_embeddings.get(ch["chunk_id"], [0.0] * 768)
        if use_postgres:
            with pg_con.cursor() as cur:
                cur.execute("""
                    INSERT INTO document_chunks (chunk_id, circular_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms, doc_type, college, school, academic_level, academic_session, target_user, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text, required_forms = EXCLUDED.required_forms, embedding = EXCLUDED.embedding,
                        college = EXCLUDED.college, school = EXCLUDED.school, academic_level = EXCLUDED.academic_level,
                        academic_session = EXCLUDED.academic_session, target_user = EXCLUDED.target_user;
                """, (ch["chunk_id"], ch["circular_id"], ch["circular_ref_no"], ch["department"], ch["status"], ch["section_heading"], ch["page_number"], ch["chunk_text"], ch["required_forms"], ch["doc_type"], ch["college"], ch["school"], ch["academic_level"], ch["academic_session"], ch["target_user"], embedding))
        else:
            sqlite_con.execute("""
                INSERT OR REPLACE INTO document_chunks (chunk_id, circular_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms, doc_type, college, school, academic_level, academic_session, target_user, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ch["chunk_id"], ch["circular_id"], ch["circular_ref_no"], ch["department"], ch["status"], ch["section_heading"], ch["page_number"], ch["chunk_text"], ch["required_forms"], ch["doc_type"], ch["college"], ch["school"], ch["academic_level"], ch["academic_session"], ch["target_user"], json.dumps(embedding)))

    if sqlite_con:
        sqlite_con.commit()
    if pg_con:
        pg_con.commit()

    # 6. Rebuild Full-Text Search FTS5 Virtual Table
    if sqlite_con:
        print("[*] Rebuilding SQLite FTS5 Full-Text Search index (Circulars + College Docs)...")
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
            SELECT chunk_id, circular_ref_no, department, section_heading, chunk_text, COALESCE(college, ''), COALESCE(school, '') FROM document_chunks;
        """)
        sqlite_con.commit()
        sqlite_con.close()

    if pg_con:
        pg_con.close()

    print("\n" + "=" * 70)
    print("  COLLEGE DOCUMENTS INGESTION & CHUNKING COMPLETE!")
    print(f"  • Documents Ingested:   {len(docs)}")
    print(f"  • Forms Ingested:       {len(forms)}")
    print(f"  • Total Chunks Indexed: {total_chunks}")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Ingest UUM College Documents and Forms into Knowledge Base")
    parser.add_argument("--force-reembed", action="store_true", help="Force re-generation of all vector embeddings")
    args = parser.parse_args()
    run_college_ingestion(force_reembed=args.force_reembed)

if __name__ == "__main__":
    main()

