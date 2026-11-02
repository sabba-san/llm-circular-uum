#!/usr/bin/env python3
"""
UUM Circular Document Ingestion & Chunking Pipeline (Phase 2)
Ingests:
1. Circulars metadata from circular_Forms_tracker.xlsx into 'circulars' table
2. Forms metadata from circular_Forms_tracker.xlsx into 'required_documents_forms' table
3. Chunks documents by clause/page and generates embeddings into 'document_chunks' table
"""

import os
import re
import time
import json
import sqlite3
import subprocess
import zipfile
import xml.etree.ElementTree as ET
import logging
from src.ai_provider import AIProvider, load_env, find_root_dir
from src.db import setup_sqlite

load_env()
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("IngestPipeline")

ROOT_DIR = find_root_dir()
EXCEL_FILE = os.path.join(ROOT_DIR, "circular_Forms_tracker.xlsx")
CACHE_FILE = os.path.join(ROOT_DIR, "data", ".metadata_cache.json")
if not os.path.exists(CACHE_FILE) and os.path.exists(os.path.join(ROOT_DIR, ".metadata_cache.json")):
    CACHE_FILE = os.path.join(ROOT_DIR, ".metadata_cache.json")
SQLITE_DB = os.path.join(ROOT_DIR, "data", "uum_knowledge.db")

def read_excel_tracker(excel_path):
    """Read circulars and forms rows from circular_Forms_tracker.xlsx."""
    circulars = []
    forms = []

    with zipfile.ZipFile(excel_path, "r") as z:
        shared_strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in sst.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                t = "".join(n.text for n in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t") if n.text)
                shared_strings.append(t)

        def parse_sheet(sheet_path):
            sheet = ET.fromstring(z.read(sheet_path))
            rows = []
            for row in sheet.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
                vals = []
                for c in row.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                    v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                    val = v.text if v is not None else ""
                    if c.attrib.get("t") == "s" and val.isdigit():
                        val = shared_strings[int(val)]
                    vals.append(val)
                rows.append(vals)
            return rows

        circ_rows = parse_sheet("xl/worksheets/sheet1.xml")
        form_rows = parse_sheet("xl/worksheets/sheet2.xml")

        for r in circ_rows[1:]:
            if len(r) >= 10:
                circulars.append({
                    "id": r[0],
                    "ref_no": r[1],
                    "title": r[2],
                    "department": r[3],
                    "category": r[4],
                    "effective_date": r[5],
                    "status": r[6],
                    "supersedes": r[7],
                    "required_forms": r[8],
                    "file_path": r[9],
                })

        for r in form_rows[1:]:
            if len(r) >= 10:
                forms.append({
                    "id": r[0],
                    "form_code": r[1],
                    "form_title": r[2],
                    "department": r[3],
                    "related_circular": r[4],
                    "project_activity_type": r[5],
                    "is_mandatory": r[6],
                    "file_path": r[7],
                    "file_format": r[8],
                    "notes": r[9],
                })

    return circulars, forms

def chunk_document(filepath, cache_meta=None):
    """Chunk document by pages and semantic sections."""
    chunks = []
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        try:
            res = subprocess.run(["pdfinfo", filepath], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            info = res.stdout.decode("utf-8", errors="ignore")
            m = re.search(r"Pages:\s+(\d+)", info)
            num_pages = int(m.group(1)) if m else 1

            for p in range(1, min(num_pages + 1, 20)):
                res_p = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), filepath, "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                txt = res_p.stdout.decode("utf-8", errors="ignore").strip()
                if len(txt) > 40:
                    paragraphs = [para.strip() for para in txt.split("\n\n") if len(para.strip()) > 30]
                    if not paragraphs:
                        paragraphs = [txt]

                    for idx, para in enumerate(paragraphs, 1):
                        heading = para.split("\n")[0][:80]
                        chunks.append({
                            "page": p,
                            "heading": heading,
                            "text": para[:1200]
                        })
        except Exception:
            pass

    elif ext == ".docx":
        try:
            with zipfile.ZipFile(filepath, "r") as z:
                xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            current_heading = "Garis Panduan"
            current_text = []

            for p in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                t = "".join(n.text for n in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if n.text).strip()
                if not t:
                    continue
                if len(t) < 70 and (t.isupper() or re.match(r"^\d+\.", t)):
                    if current_text:
                        chunks.append({"page": 1, "heading": current_heading, "text": " ".join(current_text)[:1200]})
                        current_text = []
                    current_heading = t
                else:
                    current_text.append(t)

            if current_text:
                chunks.append({"page": 1, "heading": current_heading, "text": " ".join(current_text)[:1200]})
        except Exception:
            pass

    if not chunks and cache_meta:
        raw_text = cache_meta.get("raw_text", "").strip()
        if raw_text:
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            for i in range(0, min(len(lines), 30), 6):
                sec = " ".join(lines[i:i+6])
                if len(sec) > 30:
                    chunks.append({"page": 1, "heading": lines[i][:60], "text": sec[:1000]})

    return chunks

def run_ingestion(force_reembed=False):
    ai = AIProvider()
    circulars, forms = read_excel_tracker(EXCEL_FILE)
    logger.info(f"Loaded {len(circulars)} circulars and {len(forms)} forms from {EXCEL_FILE}")

    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
        except Exception:
            pass

    db_url = os.environ.get("DATABASE_URL", "").strip()
    use_postgres = bool(db_url)
    pg_con = None
    sqlite_con = None

    if use_postgres:
        try:
            import psycopg2
            pg_con = psycopg2.connect(db_url)
            pg_con.autocommit = True
            logger.info("Connected to PostgreSQL for ingestion.")
        except Exception as e:
            logger.warning(f"Failed to connect to PostgreSQL ({e}). Using SQLite.")
            use_postgres = False

    if not use_postgres:
        setup_sqlite(SQLITE_DB)
        sqlite_con = sqlite3.connect(SQLITE_DB)
        logger.info(f"Using SQLite database: {SQLITE_DB}")

    # 1. Ingest Circulars
    print("\n[*] Ingesting circulars metadata...")
    for c in circulars:
        c_path = c["file_path"].replace("\\", "/")
        if use_postgres:
            with pg_con.cursor() as cur:
                cur.execute("""
                    INSERT INTO circulars (id, ref_no, title, department, category, effective_date, status, supersedes, required_forms, file_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        ref_no = EXCLUDED.ref_no, title = EXCLUDED.title, status = EXCLUDED.status, required_forms = EXCLUDED.required_forms, file_path = EXCLUDED.file_path;
                """, (c["id"], c["ref_no"], c["title"], c["department"], c["category"], c["effective_date"], c["status"], c["supersedes"], c["required_forms"], c_path))
        else:
            sqlite_con.execute("""
                INSERT OR REPLACE INTO circulars (id, ref_no, title, department, category, effective_date, status, supersedes, required_forms, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (c["id"], c["ref_no"], c["title"], c["department"], c["category"], c["effective_date"], c["status"], c["supersedes"], c["required_forms"], c_path))

    # 2. Ingest Forms
    print("[*] Ingesting required forms & checklists...")
    for f in forms:
        f_path = f["file_path"].replace("\\", "/")
        if use_postgres:
            with pg_con.cursor() as cur:
                cur.execute("""
                    INSERT INTO required_documents_forms (id, form_code, form_title, department, related_circular, project_activity_type, is_mandatory, file_path, file_format, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        form_code = EXCLUDED.form_code, form_title = EXCLUDED.form_title, related_circular = EXCLUDED.related_circular, file_path = EXCLUDED.file_path;
                """, (f["id"], f["form_code"], f["form_title"], f["department"], f["related_circular"], f["project_activity_type"], f["is_mandatory"], f_path, f["file_format"], f["notes"]))
        else:
            sqlite_con.execute("""
                INSERT OR REPLACE INTO required_documents_forms (id, form_code, form_title, department, related_circular, project_activity_type, is_mandatory, file_path, file_format, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f["id"], f["form_code"], f["form_title"], f["department"], f["related_circular"], f["project_activity_type"], f["is_mandatory"], f_path, f["file_format"], f["notes"]))

    # 3. Chunk Documents & Generate Embeddings
    print("[*] Parsing documents into semantic chunks...")
    chunks_to_insert = []

    for c in circulars:
        rel_path = c["file_path"].replace("\\", "/")
        full_path = os.path.join(ROOT_DIR, rel_path)
        if not os.path.exists(full_path):
            continue

        cache_meta = cache.get(full_path)
        chunks = chunk_document(full_path, cache_meta=cache_meta)

        for chk_idx, chk in enumerate(chunks, 1):
            chunk_id = f"CHK-{c['id']}-{chk_idx:03d}"
            heading = chk["heading"]
            page = chk["page"]
            text = chk["text"]

            # Clause-level form mapping
            chunk_forms = c["required_forms"]
            combined_clause = (heading + " " + text).lower()
            if "gra" in combined_clause or "pembantu penyelidik" in combined_clause:
                chunk_forms = "Borang RMC 008 (Borang Permohonan RA dan GRA)"
            elif "pendaftaran projek" in combined_clause or ("raiis" in combined_clause and "perundingan" not in combined_clause):
                chunk_forms = "Borang RMC 001 (Pendaftaran Projek RaIIS)"

            chunks_to_insert.append({
                "chunk_id": chunk_id,
                "circular_id": c["id"],
                "circular_ref_no": c["ref_no"],
                "department": c["department"],
                "status": c["status"],
                "section_heading": heading,
                "page_number": page,
                "chunk_text": text,
                "required_forms": chunk_forms,
                "embed_input": f"{c['ref_no']}: {heading}\n{text}"
            })

    total_chunks = len(chunks_to_insert)

    # 4. Check existing embeddings for incremental ingestion
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
        print(f"[*] Found {len(new_chunks)} new/unembedded chunks out of {total_chunks} total. Generating embeddings...")
        batch_size = 50
        delay = 4.2
        total_batches = (len(new_chunks) + batch_size - 1) // batch_size
        for b_idx in range(total_batches):
            start = b_idx * batch_size
            batch = new_chunks[start:start + batch_size]
            batch_texts = [ch["embed_input"] for ch in batch]
            batch_embs = ai.batch_get_embeddings(batch_texts, batch_size=batch_size, delay=0)
            for idx, ch in enumerate(batch):
                emb = batch_embs[idx] if idx < len(batch_embs) else [0.0] * 768
                existing_embeddings[ch["chunk_id"]] = emb
            print(f"  [+] Embedded {min(start + batch_size, len(new_chunks))}/{len(new_chunks)} new chunks")
            if b_idx + 1 < total_batches and delay > 0:
                time.sleep(delay)
    else:
        print(f"[*] All {total_chunks} chunks already have valid embeddings. (Incremental skip)")

    print(f"[*] Storing {total_chunks} chunks into database...")
    for ch in chunks_to_insert:
        embedding = existing_embeddings.get(ch["chunk_id"], [0.0] * 768)
        if use_postgres:
            with pg_con.cursor() as cur:
                cur.execute("""
                    INSERT INTO document_chunks (chunk_id, circular_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text, required_forms = EXCLUDED.required_forms, embedding = EXCLUDED.embedding;
                """, (ch["chunk_id"], ch["circular_id"], ch["circular_ref_no"], ch["department"], ch["status"], ch["section_heading"], ch["page_number"], ch["chunk_text"], ch["required_forms"], embedding))
        else:
            sqlite_con.execute("""
                INSERT OR REPLACE INTO document_chunks (chunk_id, circular_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ch["chunk_id"], ch["circular_id"], ch["circular_ref_no"], ch["department"], ch["status"], ch["section_heading"], ch["page_number"], ch["chunk_text"], ch["required_forms"], json.dumps(embedding)))

    if sqlite_con:
        sqlite_con.commit()
    if pg_con:
        pg_con.commit()

    if sqlite_con:
        print("[*] Building SQLite FTS5 Full-Text Search index...")
        sqlite_con.execute("DROP TABLE IF EXISTS chunks_fts;")
        sqlite_con.execute("""
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                chunk_id UNINDEXED,
                circular_ref_no,
                department,
                section_heading,
                chunk_text
            );
        """)
        sqlite_con.execute("""
            INSERT INTO chunks_fts (chunk_id, circular_ref_no, department, section_heading, chunk_text)
            SELECT chunk_id, circular_ref_no, department, section_heading, chunk_text FROM document_chunks;
        """)
        sqlite_con.commit()
        sqlite_con.close()

    if pg_con:
        pg_con.close()

    print("\n" + "=" * 70)
    print("  INGESTION & CHUNKING COMPLETE!")
    print(f"  • Circulars Ingested:    {len(circulars)}")
    print(f"  • Forms Ingested:        {len(forms)}")
    print(f"  • Total Chunks Indexed:  {total_chunks}")
    print("=" * 70)

if __name__ == "__main__":
    run_ingestion()

