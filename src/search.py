#!/usr/bin/env python3
"""
UUM Circular & Project Document Intelligence Assistant (Phase 3)
Interactive Query CLI with Hybrid Retrieval (BM25 + Semantic Vector Search)
"""

import os
import sys
import json
import re
import sqlite3
import argparse
import math
from src.ai_provider import AIProvider, load_env, find_root_dir, is_english_query

load_env()

ROOT_DIR = find_root_dir()
SQLITE_DB = os.path.join(ROOT_DIR, "data", "uum_knowledge.db")

ENGLISH_TO_MALAY_EXPANSION = {
    "gra": ["gra", "pembantu", "penyelidik", "siswazah", "lantikan", "rmc 008"],
    "graduate": ["siswazah", "pembantu", "penyelidik"],
    "research": ["penyelidikan", "geran", "projek", "rmc"],
    "assistant": ["pembantu", "penyelidik", "ra", "gra", "lantikan"],
    "appoint": ["lantikan", "permohonan", "syarat", "vot 11000"],
    "appointment": ["lantikan", "permohonan", "syarat", "rmc 008", "vot 11000"],
    "claim": ["tuntutan", "kadar", "bayaran"],
    "claims": ["tuntutan", "kadar", "bayaran"],
    "travel": ["perjalanan", "perbatuan", "elaun", "tambang"],
    "speaker": ["penceramah", "saguhati", "pensyarah"],
    "external": ["luar", "swasta", "agensi"],
    "honorarium": ["saguhati", "kadar", "bayaran", "penceramah", "pensyarah"],
    "asset": ["aset", "harta", "kew.pa"],
    "disposal": ["pelupusan", "hapuskira", "kew.pa"],
    "procurement": ["perolehan", "pesanan", "pembekal", "pk 7"],
    "quotation": ["sebutharga", "tender", "perolehan"],
    "tender": ["tender", "sebutharga", "perolehan"],
    "salary": ["gaji", "upah", "elaun"],
    "allowance": ["elaun", "upah", "vot 11000"],
    "medical": ["rawatan", "perubatan", "klinik"],
    "conference": ["persidangan", "seminar", "bengkel"],
    "consultancy": ["perundingan", "raiis", "rmc 019"],
    "advance": ["pendahuluan", "diri"],
    "cash": ["wang", "runcit", "panjar"],
    "form": ["borang"],
    "forms": ["borang"],
    "rules": ["garis", "panduan", "pekeliling", "syarat"],
    "requirement": ["syarat", "kelayakan"],
    "requirements": ["syarat", "kelayakan", "vot 11000"],
    # Academic & College Handbooks Expansion
    "handbook": ["panduan", "akademik", "buku"],
    "calendar": ["kalendar", "akademik", "semester", "sesi"],
    "curriculum": ["kurikulum", "kursus", "struktur", "kredit", "teras", "elektif"],
    "credit": ["kredit", "jam", "kursus"],
    "credits": ["kredit", "jam", "kursus"],
    "graduation": ["pengijazahan", "bergraduat", "syarat", "taraf"],
    "undergraduate": ["sarjana", "muda", "prasiswazah", "ug"],
    "postgraduate": ["siswazah", "pascasiswazah", "sarjana", "phd", "doktor", "falsafah", "pg"],
    "internship": ["praktikum", "latihan", "industri", "pli"],
    "practicum": ["praktikum", "latihan", "industri", "majikan"],
    "minor": ["minor", "elektif", "pendaftaran"],
    "thesis": ["tesis", "disertasi", "cadangan", "viva", "ahsgs", "gsgsg"],
    "dissertation": ["disertasi", "tesis", "viva"],
    "deferment": ["tangguh", "pengajian", "penangguhan"],
}

def expand_query_tokens(query):
    """Expand query tokens with cross-lingual UUM administrative domain keywords."""
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", query.lower())
    words = clean.split()
    expanded = set(words)
    for w in words:
        if w in ENGLISH_TO_MALAY_EXPANSION:
            expanded.update(ENGLISH_TO_MALAY_EXPANSION[w])
    return [w for w in expanded if len(w) > 2]

def cosine_similarity(v1, v2):
    """Compute cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1)) or 1.0
    norm2 = math.sqrt(sum(b * b for b in v2)) or 1.0
    return dot / (norm1 * norm2)

class UUMAssistant:
    def __init__(self):
        self.ai = AIProvider()
        self.db_url = os.environ.get("DATABASE_URL", "").strip()
        self.use_postgres = bool(self.db_url)
        self.pg_con = None
        self.sqlite_con = None

        if self.use_postgres:
            try:
                import psycopg2
                self.pg_con = psycopg2.connect(self.db_url)
            except Exception:
                self.use_postgres = False

        if not self.use_postgres:
            if not os.path.exists(SQLITE_DB):
                raise FileNotFoundError(f"Database not found at {SQLITE_DB}. Please run ingest.py first.")
            self.sqlite_con = sqlite3.connect(SQLITE_DB, timeout=60.0, check_same_thread=False)
            self.sqlite_con.row_factory = sqlite3.Row

        self.doc_registry, self.forms_list = self._load_doc_registry()

    def _load_doc_registry(self):
        """Build lookup dictionary mapping document/form IDs to file_path, format, and metadata."""
        registry = {}
        forms_list = []
        if not self.sqlite_con:
            return registry, forms_list

        cur = self.sqlite_con.cursor()
        try:
            cur.execute("SELECT id, ref_no, title, department, category, effective_date, status, required_forms, file_path FROM circulars;")
            for r in cur.fetchall():
                fp = (r["file_path"] or "").replace("\\", "/")
                ext = os.path.splitext(fp)[1].lstrip(".").upper() or "PDF"
                registry[r["id"]] = {
                    "doc_id": r["id"],
                    "code": r["ref_no"],
                    "title": r["title"],
                    "department": r["department"],
                    "category": r["category"] or "Circular",
                    "session": r["effective_date"] or "",
                    "status": r["status"] or "Active",
                    "file_path": fp,
                    "file_format": ext,
                    "doc_type": "circular",
                    "college": r["department"],
                    "school": r["department"],
                    "academic_level": "University-Wide",
                }
        except Exception:
            pass

        try:
            cur.execute("SELECT id, form_code, form_title, department, related_circular, project_activity_type, is_mandatory, file_path, file_format FROM required_documents_forms;")
            for r in cur.fetchall():
                fp = (r["file_path"] or "").replace("\\", "/")
                ext = (r["file_format"] or os.path.splitext(fp)[1].lstrip(".")).upper() or "PDF"
                entry = {
                    "doc_id": r["id"],
                    "code": r["form_code"],
                    "title": r["form_title"],
                    "department": r["department"],
                    "category": r["project_activity_type"] or "Admin Form",
                    "session": "Current",
                    "status": "Active",
                    "file_path": fp,
                    "file_format": ext,
                    "doc_type": "admin_form",
                    "college": r["department"],
                    "school": r["department"],
                    "academic_level": "Staff / Researcher",
                    "is_mandatory": r["is_mandatory"] or "Mandatory",
                }
                registry[r["id"]] = entry
                forms_list.append(entry)
        except Exception:
            pass

        try:
            cur.execute("SELECT id, title, college, school, category, academic_level, academic_session, status, file_format, file_path FROM college_documents;")
            for r in cur.fetchall():
                fp = (r["file_path"] or "").replace("\\", "/")
                ext = (r["file_format"] or os.path.splitext(fp)[1].lstrip(".")).upper() or "PDF"
                registry[r["id"]] = {
                    "doc_id": r["id"],
                    "code": r["id"],
                    "title": r["title"],
                    "department": f"{r['college']} — {r['school']}",
                    "category": r["category"] or "Academic Document",
                    "session": r["academic_session"] or "Current",
                    "status": r["status"] or "Active",
                    "file_path": fp,
                    "file_format": ext,
                    "doc_type": "college_doc",
                    "college": r["college"],
                    "school": r["school"],
                    "academic_level": r["academic_level"] or "All Levels",
                }
        except Exception:
            pass

        try:
            cur.execute("SELECT id, form_code, form_title, college, school, form_category, target_user, academic_session, file_format, file_path FROM college_forms;")
            for r in cur.fetchall():
                fp = (r["file_path"] or "").replace("\\", "/")
                ext = (r["file_format"] or os.path.splitext(fp)[1].lstrip(".")).upper() or "PDF"
                entry = {
                    "doc_id": r["id"],
                    "code": r["form_code"],
                    "title": r["form_title"],
                    "department": f"{r['college']} — {r['school']}",
                    "category": r["form_category"] or "College Form",
                    "session": r["academic_session"] or "Current",
                    "status": "Active",
                    "file_path": fp,
                    "file_format": ext,
                    "doc_type": "college_form",
                    "college": r["college"],
                    "school": r["school"],
                    "academic_level": r["target_user"] or "Student / Staff",
                    "is_mandatory": "Mandatory",
                }
                registry[r["id"]] = entry
                forms_list.append(entry)
        except Exception:
            pass

        return registry, forms_list

    def _match_Scope(self, chunk_row, scope):
        """Check whether a chunk matches the user-selected scope filter pill."""
        if not scope or scope.lower() in ("all", "all uum"):
            return True
        s = scope.lower()
        dept = (chunk_row.get("department") or "").lower()
        col = (chunk_row.get("college") or "").lower()
        sch = (chunk_row.get("school") or "").lower()
        dtype = (chunk_row.get("doc_type") or "circular").lower()

        if s == "circulars":
            return dtype == "circular"
        if s == "colleges":
            return dtype in ("college_doc", "college_form")
        if s == "cas":
            return "cas" in col or "cas" in dept
        if s == "cob":
            return "cob" in col or "cob" in dept
        if s == "colgis":
            return "colgis" in col or "colgis" in dept
        if s in ("hea", "shared", "uni"):
            return "shared" in col or "hea" in dept or "hea" in sch or "cuic" in dept
        if s == "rmc":
            return "rmc" in dept or "research management" in dept
        if s == "bendahari":
            return "bendahari" in dept
        if s == "icc":
            return "icc" in dept or "innovation" in dept
        if s == "juu":
            return "juu" in dept or "undang" in dept
        return s in dept or s in col or s in sch

    def _resolve_linked_forms(self, required_forms_str, circular_id=None):
        """Find matching downloadable form records for a chunk's required_forms string."""
        linked = []
        seen = set()
        if circular_id and circular_id in self.doc_registry:
            meta = self.doc_registry[circular_id]
            if meta.get("doc_type") in ("admin_form", "college_form"):
                linked.append(meta)
                seen.add(meta["doc_id"])

        if not required_forms_str or required_forms_str.strip() in ("-", "None", "Tiada", ""):
            return linked

        rf_low = required_forms_str.lower()
        for fm in self.forms_list:
            if fm["doc_id"] in seen:
                continue
            code_low = fm["code"].lower()
            title_low = fm["title"].lower()
            if (len(code_low) >= 4 and code_low in rf_low) or (len(title_low) >= 10 and title_low[:25] in rf_low):
                linked.append(fm)
                seen.add(fm["doc_id"])
        return linked[:4]

    def _enrich_chunk(self, chk):
        """Attach file_path, file_format, college, school, and linked_forms to a retrieved chunk."""
        cid = chk.get("circular_id")
        meta = self.doc_registry.get(cid, {})
        chk["doc_id"] = cid or chk.get("chunk_id", "")
        chk["title"] = meta.get("title") or chk.get("circular_ref_no") or "UUM Document"
        chk["file_path"] = meta.get("file_path", "")
        chk["file_format"] = meta.get("file_format", "PDF")
        chk["doc_type"] = chk.get("doc_type") or meta.get("doc_type", "circular")
        chk["college"] = chk.get("college") or meta.get("college") or chk.get("department", "UUM")
        chk["school"] = chk.get("school") or meta.get("school") or ""
        chk["academic_level"] = chk.get("academic_level") or meta.get("academic_level") or ""
        chk["academic_session"] = chk.get("academic_session") or meta.get("session") or ""
        chk["category"] = meta.get("category", "Document")
        chk["linked_forms"] = self._resolve_linked_forms(chk.get("required_forms", ""), cid)
        return chk

    def hybrid_search(self, query, top_k=6, filter_active=True, scope="All"):
        """Perform hybrid BM25 + Dense Semantic search across UUM circular & college chunks."""
        q_vec = self.ai.get_embedding(query)
        expanded_tokens = expand_query_tokens(query)
        fts_query = " OR ".join(expanded_tokens[:12]) if expanded_tokens else query
        candidates = {}

        if self.use_postgres:
            with self.pg_con.cursor() as cur:
                # 1. BM25 Search
                cur.execute("""
                    SELECT chunk_id, circular_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms,
                           doc_type, college, school, academic_level, academic_session,
                           ts_rank_cd(tsv_content, websearch_to_tsquery('simple', %s)) AS bm25_score
                    FROM document_chunks
                    WHERE (%s = FALSE OR status = 'Active') AND tsv_content @@ websearch_to_tsquery('simple', %s)
                    ORDER BY bm25_score DESC LIMIT 40;
                """, (query, filter_active, query))
                for row in cur.fetchall():
                    item = {
                        "chunk_id": row[0],
                        "circular_id": row[1],
                        "circular_ref_no": row[2],
                        "department": row[3],
                        "status": row[4],
                        "section_heading": row[5],
                        "page_number": row[6],
                        "chunk_text": row[7],
                        "required_forms": row[8],
                        "doc_type": row[9],
                        "college": row[10],
                        "school": row[11],
                        "academic_level": row[12],
                        "academic_session": row[13],
                        "bm25_score": float(row[14]),
                        "vec_score": 0.0,
                    }
                    if self._match_Scope(item, scope):
                        candidates[row[0]] = item

                # 2. Vector Cosine Search
                cur.execute("""
                    SELECT chunk_id, circular_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms,
                           doc_type, college, school, academic_level, academic_session,
                           1 - (embedding <=> %s::vector) AS sim_score
                    FROM document_chunks
                    WHERE (%s = FALSE OR status = 'Active')
                    ORDER BY embedding <=> %s::vector ASC LIMIT 40;
                """, (q_vec, filter_active, q_vec))
                for row in cur.fetchall():
                    cid = row[0]
                    sim = float(row[14])
                    if cid in candidates:
                        candidates[cid]["vec_score"] = sim
                    else:
                        item = {
                            "chunk_id": cid,
                            "circular_id": row[1],
                            "circular_ref_no": row[2],
                            "department": row[3],
                            "status": row[4],
                            "section_heading": row[5],
                            "page_number": row[6],
                            "chunk_text": row[7],
                            "required_forms": row[8],
                            "doc_type": row[9],
                            "college": row[10],
                            "school": row[11],
                            "academic_level": row[12],
                            "academic_session": row[13],
                            "bm25_score": 0.0,
                            "vec_score": sim,
                        }
                        if self._match_Scope(item, scope):
                            candidates[cid] = item
        else:
            # SQLite FTS5 Search (with expanded tokens)
            try:
                cur = self.sqlite_con.cursor()
                cur.execute("""
                    SELECT c.chunk_id, c.circular_id, c.circular_ref_no, c.department, c.status, c.section_heading, c.page_number, c.chunk_text, c.required_forms,
                           c.doc_type, c.college, c.school, c.academic_level, c.academic_session, c.embedding_json,
                           rank AS bm25_rank
                    FROM chunks_fts f
                    JOIN document_chunks c ON f.chunk_id = c.chunk_id
                    WHERE chunks_fts MATCH ? AND (? = 0 OR c.status = 'Active')
                    ORDER BY rank LIMIT 60;
                """, (fts_query, 1 if filter_active else 0))
                for r in cur.fetchall():
                    cid = r["chunk_id"]
                    item = {
                        "chunk_id": cid,
                        "circular_id": r["circular_id"],
                        "circular_ref_no": r["circular_ref_no"],
                        "department": r["department"],
                        "status": r["status"],
                        "section_heading": r["section_heading"],
                        "page_number": r["page_number"],
                        "chunk_text": r["chunk_text"],
                        "required_forms": r["required_forms"],
                        "doc_type": r["doc_type"],
                        "college": r["college"],
                        "school": r["school"],
                        "academic_level": r["academic_level"],
                        "academic_session": r["academic_session"],
                    }
                    if not self._match_Scope(item, scope):
                        continue
                    vec = json.loads(r["embedding_json"]) if r["embedding_json"] else []
                    sim = cosine_similarity(q_vec, vec) if vec else 0.0
                    item["bm25_score"] = abs(float(r["bm25_rank"]))
                    item["vec_score"] = sim
                    candidates[cid] = item
            except Exception:
                pass

            # SQLite Vector scanning across active chunks to catch semantic matches
            cur = self.sqlite_con.cursor()
            cur.execute("""
                SELECT chunk_id, circular_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms,
                       doc_type, college, school, academic_level, academic_session, embedding_json
                FROM document_chunks
                WHERE (? = 0 OR status = 'Active')
            """, (1 if filter_active else 0,))

            vector_candidates = []
            for r in cur.fetchall():
                cid = r["chunk_id"]
                if cid in candidates:
                    continue
                item = {
                    "chunk_id": cid,
                    "circular_id": r["circular_id"],
                    "circular_ref_no": r["circular_ref_no"],
                    "department": r["department"],
                    "status": r["status"],
                    "section_heading": r["section_heading"],
                    "page_number": r["page_number"],
                    "chunk_text": r["chunk_text"],
                    "required_forms": r["required_forms"],
                    "doc_type": r["doc_type"],
                    "college": r["college"],
                    "school": r["school"],
                    "academic_level": r["academic_level"],
                    "academic_session": r["academic_session"],
                }
                if not self._match_Scope(item, scope):
                    continue
                vec = json.loads(r["embedding_json"]) if r["embedding_json"] else []
                if vec:
                    sim = cosine_similarity(q_vec, vec)
                    if sim > 0.38:
                        vector_candidates.append((sim, item))

            vector_candidates.sort(key=lambda x: x[0], reverse=True)
            for sim, item in vector_candidates[:35]:
                cid = item["chunk_id"]
                item["bm25_score"] = 0.0
                item["vec_score"] = sim
                candidates[cid] = item

        results = list(candidates.values())
        max_bm25 = max([c["bm25_score"] for c in results], default=1.0) or 1.0
        for c in results:
            c["combined_score"] = round((0.6 * c["vec_score"]) + (0.4 * (c["bm25_score"] / max_bm25)), 4)
            self._enrich_chunk(c)

        results.sort(key=lambda x: x["combined_score"], reverse=True)
        return results[:top_k]

    def get_document_preview(self, doc_id):
        """Return full metadata and extracted sections/clauses for any document or form ID."""
        meta = self.doc_registry.get(doc_id)
        if not meta:
            for k, v in self.doc_registry.items():
                if v.get("code") == doc_id or v.get("file_path") == doc_id:
                    meta = v
                    doc_id = k
                    break

        if not meta:
            return None

        sections = []
        if self.sqlite_con:
            cur = self.sqlite_con.cursor()
            cur.execute("""
                SELECT chunk_id, section_heading, page_number, chunk_text
                FROM document_chunks
                WHERE circular_id = ?
                ORDER BY page_number ASC, chunk_id ASC
                LIMIT 80;
            """, (doc_id,))
            for r in cur.fetchall():
                sections.append({
                    "chunk_id": r["chunk_id"],
                    "heading": r["section_heading"] or f"Page {r['page_number']}",
                    "page": r["page_number"] or 1,
                    "text": r["chunk_text"],
                })

        if not sections and meta.get("file_path"):
            full_path = os.path.join(ROOT_DIR, meta["file_path"])
            if os.path.exists(full_path):
                try:
                    from src.college_extractor import extract_document_chunks
                    raw_chunks = extract_document_chunks(full_path, max_pages=15)
                    for idx, sc in enumerate(raw_chunks, 1):
                        sections.append({
                            "chunk_id": f"{doc_id}-P{idx}",
                            "heading": sc.get("heading", f"Section {idx}"),
                            "page": sc.get("page", 1),
                            "text": sc.get("text", ""),
                        })
                except Exception:
                    pass

        return {
            "meta": meta,
            "sections": sections,
        }

    def ask(self, query, filter_active=True, scope="All", top_k=6):
        """Ask question and generate grounded response with strict citations and linked files."""
        retrieved = self.hybrid_search(query, top_k=top_k, filter_active=filter_active, scope=scope)

        if not retrieved:
            if is_english_query(query):
                msg = "No official circulars, academic handbooks, or forms were found matching your query and scope filter. Try broadening your scope to 'All UUM' or contact the responsible PTJ / College."
            else:
                msg = "Tiada pekeliling, buku panduan akademik, atau borang rasmi yang ditemui bagi carian dan tapisan ini. Sila cuba tapisan 'All UUM' atau hubungi PTJ / Kolej berkenaan."
            return {
                "answer": msg,
                "provider": "None",
                "sources": [],
                "linked_forms": [],
                "query": query,
                "scope": scope,
            }

        response_text, provider_name = self.ai.generate_chat_response(query, retrieved)

        # Deduplicate linked forms across all retrieved sources
        all_forms = []
        seen_fids = set()
        for s in retrieved:
            for fm in s.get("linked_forms", []):
                if fm["doc_id"] not in seen_fids:
                    all_forms.append(fm)
                    seen_fids.add(fm["doc_id"])

        return {
            "answer": response_text,
            "provider": provider_name,
            "sources": retrieved,
            "linked_forms": all_forms,
            "query": query,
            "scope": scope,
        }

def print_result(res):
    query = res.get("query", "")
    is_en = is_english_query(query)
    print("\n" + "=" * 75)
    if is_en:
        print("  UUM DOCUMENT INTELLIGENCE ASSISTANT (RAG)")
    else:
        print("  PEMBANTU PINTAR DOKUMEN & PEKELILING UUM (RAG)")
    print("=" * 75)
    print(res["answer"])
    print("\n" + "-" * 75)
    print(f"  [AI Engine: {res['provider']}]")
    if is_en:
        print("  Official UUM Sources & Citations:")
        for idx, s in enumerate(res["sources"], 1):
            forms = s.get("required_forms", "-")
            forms_str = f" | Forms: {forms}" if forms and forms != "-" else ""
            print(f"   [{idx}] {s['circular_ref_no']} ({s['department']}) - Page {s['page_number']}: {s['section_heading']}{forms_str}")
    else:
        print("  Rujukan Sumber Rasmi UUM (Citations):")
        for idx, s in enumerate(res["sources"], 1):
            forms = s.get("required_forms", "-")
            forms_str = f" | Borang: {forms}" if forms and forms != "-" else ""
            print(f"   [{idx}] {s['circular_ref_no']} ({s['department']}) - M/S {s['page_number']}: {s['section_heading']}{forms_str}")
    print("=" * 75 + "\n")

