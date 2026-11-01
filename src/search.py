#!/usr/bin/env python3
"""
UUM Circular & Project Document Intelligence Assistant (Phase 3)
Interactive Query CLI with Hybrid Retrieval (BM25 + Semantic Vector Search)
"""

import os
import sys
import json
import sqlite3
import argparse
import math
from src.ai_provider import AIProvider, load_env, find_root_dir

load_env()

ROOT_DIR = find_root_dir()
SQLITE_DB = os.path.join(ROOT_DIR, "data", "uum_knowledge.db")

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
            self.sqlite_con = sqlite3.connect(SQLITE_DB)
            self.sqlite_con.row_factory = sqlite3.Row

    def hybrid_search(self, query, top_k=5, filter_active=True):
        """Perform hybrid BM25 + Dense Semantic search across UUM circular chunks."""
        q_vec = self.ai.get_embedding(query)
        clean_tokens = [w for w in query.replace("?", "").replace("'", "").replace('"', "").split() if len(w) > 2]
        fts_query = " OR ".join(clean_tokens[:6]) if clean_tokens else query
        candidates = {}

        if self.use_postgres:
            with self.pg_con.cursor() as cur:
                # 1. BM25 Search
                cur.execute("""
                    SELECT chunk_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms,
                           ts_rank_cd(tsv_content, websearch_to_tsquery('simple', %s)) AS bm25_score
                    FROM document_chunks
                    WHERE (%s = FALSE OR status = 'Active') AND tsv_content @@ websearch_to_tsquery('simple', %s)
                    ORDER BY bm25_score DESC LIMIT 20;
                """, (filter_active, query))
                for row in cur.fetchall():
                    cid = row[0]
                    candidates[cid] = {
                        "chunk_id": cid,
                        "circular_ref_no": row[1],
                        "department": row[2],
                        "status": row[3],
                        "section_heading": row[4],
                        "page_number": row[5],
                        "chunk_text": row[6],
                        "required_forms": row[7],
                        "bm25_score": float(row[8]),
                        "vec_score": 0.0,
                    }

                # 2. Vector Cosine Search
                cur.execute("""
                    SELECT chunk_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms,
                           1 - (embedding <=> %s::vector) AS sim_score
                    FROM document_chunks
                    WHERE (%s = FALSE OR status = 'Active')
                    ORDER BY embedding <=> %s::vector ASC LIMIT 20;
                """, (q_vec, filter_active, q_vec))
                for row in cur.fetchall():
                    cid = row[0]
                    sim = float(row[8])
                    if cid in candidates:
                        candidates[cid]["vec_score"] = sim
                    else:
                        candidates[cid] = {
                            "chunk_id": cid,
                            "circular_ref_no": row[1],
                            "department": row[2],
                            "status": row[3],
                            "section_heading": row[4],
                            "page_number": row[5],
                            "chunk_text": row[6],
                            "required_forms": row[7],
                            "bm25_score": 0.0,
                            "vec_score": sim,
                        }
        else:
            # SQLite FTS5 Search
            try:
                cur = self.sqlite_con.cursor()
                cur.execute("""
                    SELECT c.chunk_id, c.circular_ref_no, c.department, c.status, c.section_heading, c.page_number, c.chunk_text, c.required_forms, c.embedding_json,
                           rank AS bm25_rank
                    FROM chunks_fts f
                    JOIN document_chunks c ON f.chunk_id = c.chunk_id
                    WHERE chunks_fts MATCH ? AND (? = 0 OR c.status = 'Active')
                    ORDER BY rank LIMIT 25;
                """, (fts_query, 1 if filter_active else 0))
                for r in cur.fetchall():
                    cid = r["chunk_id"]
                    vec = json.loads(r["embedding_json"]) if r["embedding_json"] else []
                    sim = cosine_similarity(q_vec, vec) if vec else 0.0
                    candidates[cid] = {
                        "chunk_id": cid,
                        "circular_ref_no": r["circular_ref_no"],
                        "department": r["department"],
                        "status": r["status"],
                        "section_heading": r["section_heading"],
                        "page_number": r["page_number"],
                        "chunk_text": r["chunk_text"],
                        "required_forms": r["required_forms"],
                        "bm25_score": abs(float(r["bm25_rank"])),
                        "vec_score": sim,
                    }
            except Exception:
                pass

            # SQLite Vector scanning
            cur = self.sqlite_con.cursor()
            cur.execute("SELECT chunk_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms, embedding_json FROM document_chunks WHERE (? = 0 OR status = 'Active') LIMIT 60;", (1 if filter_active else 0,))
            for r in cur.fetchall():
                cid = r["chunk_id"]
                if cid not in candidates:
                    vec = json.loads(r["embedding_json"]) if r["embedding_json"] else []
                    sim = cosine_similarity(q_vec, vec) if vec else 0.0
                    candidates[cid] = {
                        "chunk_id": cid,
                        "circular_ref_no": r["circular_ref_no"],
                        "department": r["department"],
                        "status": r["status"],
                        "section_heading": r["section_heading"],
                        "page_number": r["page_number"],
                        "chunk_text": r["chunk_text"],
                        "required_forms": r["required_forms"],
                        "bm25_score": 0.0,
                        "vec_score": sim,
                    }

        results = list(candidates.values())
        max_bm25 = max([c["bm25_score"] for c in results], default=1.0) or 1.0
        for c in results:
            c["combined_score"] = (0.6 * c["vec_score"]) + (0.4 * (c["bm25_score"] / max_bm25))

        results.sort(key=lambda x: x["combined_score"], reverse=True)
        return results[:top_k]

    def ask(self, query):
        """Ask question and generate grounded response with strict citations."""
        retrieved = self.hybrid_search(query, top_k=4, filter_active=True)

        if not retrieved:
            return {
                "answer": "Tiada pekeliling atau garis panduan rasmi yang ditemui berkaitan carian anda. Sila hubungi Pegawai Pusat Tanggungjawab (PTJ) berkenaan untuk maklumat lanjut.",
                "provider": "None",
                "sources": []
            }

        response_text, provider_name = self.ai.generate_chat_response(query, retrieved)
        return {
            "answer": response_text,
            "provider": provider_name,
            "sources": retrieved
        }

def print_result(res):
    print("\n" + "=" * 75)
    print("  UUM DOCUMENT INTELLIGENCE ASSISTANT (RAG)")
    print("=" * 75)
    print(res["answer"])
    print("\n" + "-" * 75)
    print(f"  [AI Engine: {res['provider']}]")
    print("  Rujukan Sumber Rasmi UUM (Citations):")
    for idx, s in enumerate(res["sources"], 1):
        forms = s.get("required_forms", "-")
        forms_str = f" | Borang: {forms}" if forms and forms != "-" else ""
        print(f"   [{idx}] {s['circular_ref_no']} ({s['department']}) - M/S {s['page_number']}: {s['section_heading']}{forms_str}")
    print("=" * 75 + "\n")

