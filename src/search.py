#!/usr/bin/env python3
"""
UUM Circular & Project Document Intelligence Assistant (Phase 3)
Interactive Query CLI with Hybrid Retrieval (BM25 + Semantic Vector Search)
"""

import os
import json
import re
import sqlite3
import logging
import math
import threading
from typing import Any
import numpy as np
from src.ai_provider import AIProvider, load_env, find_root_dir, is_english_query
from src.db import get_sqlite_path

load_env()
logger = logging.getLogger("SearchEngine")

ROOT_DIR = find_root_dir()
SQLITE_DB = get_sqlite_path()

ENGLISH_TO_MALAY_EXPANSION = {
    "gra": ["gra", "pembantu", "penyelidik", "siswazah", "lantikan", "rmc008"],
    "graduate": ["siswazah", "pembantu", "penyelidik"],
    "research": ["penyelidikan", "geran", "projek", "rmc"],
    "assistant": ["pembantu", "penyelidik", "ra", "gra", "lantikan"],
    "appoint": ["lantikan", "permohonan", "syarat", "vot"],
    "appointment": ["lantikan", "permohonan", "syarat", "vot"],
    "claim": ["tuntutan", "kadar", "bayaran"],
    "claims": ["tuntutan", "kadar", "bayaran"],
    "travel": ["perjalanan", "perbatuan", "elaun", "tambang"],
    "speaker": ["penceramah", "saguhati", "pensyarah"],
    "external": ["luar", "swasta", "agensi"],
    "honorarium": ["saguhati", "kadar", "bayaran", "penceramah", "pensyarah"],
    "asset": ["aset", "harta", "kew.pa"],
    "disposal": ["pelupusan", "hapuskira", "kew.pa"],
    "procurement": ["perolehan", "pesanan", "pembekal"],
    "quotation": ["sebutharga", "tender", "perolehan"],
    "tender": ["tender", "sebutharga", "perolehan"],
    "salary": ["gaji", "upah", "elaun"],
    "allowance": ["elaun", "upah", "vot"],
    "medical": ["rawatan", "perubatan", "klinik"],
    "conference": ["persidangan", "seminar", "bengkel"],
    "consultancy": ["perundingan", "raiis"],
    "advance": ["pendahuluan", "diri"],
    "cash": ["wang", "runcit", "panjar", "tunai"],
    "form": ["borang"],
    "forms": ["borang"],
    "intention": ["intent", "intention", "submission", "proposal", "ahsgs"],
    "rules": ["garis", "panduan", "pekeliling", "syarat"],
    "requirement": ["syarat", "kelayakan"],
    "requirements": ["syarat", "kelayakan"],
    "bursar": ["bendahari", "bursar"],
    "bendahari": ["bursar", "bendahari"],
    "circular": ["pekeliling", "circular"],
    "pekeliling": ["circular", "pekeliling"],
    "budget": ["belanjawan", "peruntukan", "kawalan"],
    "expenditure": ["perbelanjaan", "penjimatan", "kawalan"],
    "saving": ["penjimatan", "kawalan"],
    "meal": ["jamuan", "makan", "keraian"],
    "refreshment": ["jamuan", "keraian", "makan"],
    "emolumen": ["emolument", "emolumen", "gaji"],
    "emolument": ["emolumen", "emolument", "gaji"],
    "pelawat": ["visiting", "pelawat"],
    "visiting": ["pelawat", "visiting"],
    "scholars": ["pensyarah", "scholars"],
    "grant": ["geran", "dana"],
    "geran": ["grant", "geran"],
    "elective": ["elektif", "bebas"],
    "elektif": ["elective", "elektif"],
    # Academic & College Handbooks Expansion
    "handbook": ["panduan", "akademik", "buku"],
    "calendar": ["kalendar", "akademik", "semester", "sesi"],
    "kalendar": ["calendar", "kalendar", "akademik"],
    "curriculum": ["kurikulum", "kursus", "struktur", "kredit", "teras", "elektif"],
    "credit": ["kredit", "jam", "kursus"],
    "credits": ["kredit", "jam", "kursus"],
    "graduation": ["pengijazahan", "bergraduat", "syarat", "taraf"],
    "undergraduate": ["sarjana", "muda", "prasiswazah", "ug"],
    "postgraduate": ["siswazah", "pascasiswazah", "sarjana", "phd", "doktor", "falsafah", "pg"],
    "internship": ["praktikum", "latihan", "industri", "pli"],
    "practicum": ["praktikum", "latihan", "industri", "majikan"],
    "praktikum": ["practicum", "praktikum", "employer", "employers"],
    "minor": ["minor", "elektif", "pendaftaran"],
    "thesis": ["tesis", "disertasi", "cadangan", "viva", "ahsgs", "gsgsg"],
    "dissertation": ["disertasi", "tesis", "viva"],
    "deferment": ["tangguh", "pengajian", "penangguhan"],
    "struktur": ["structure", "programme", "curriculum", "core"],
    "kursus": ["course", "courses", "curriculum", "structure"],
    "sarjana": ["bachelor", "master", "degree", "honours"],
    "muda": ["bachelor", "undergraduate", "honours"],
    "teknologi": ["technology", "information", "it", "multimedia"],
    "maklumat": ["information", "technology", "it"],
    "kepujian": ["honours", "hons", "bachelor"],
    "pengkomputeran": ["computing", "computer", "soc"],
    "komputer": ["computer", "computing", "soc"],
    "sains": ["science", "bsc", "bachelor"],
}

QUERY_STOPWORDS = {
    "what", "which", "where", "when", "who", "whom", "whose", "why", "how",
    "the", "and", "for", "are", "was", "were", "with", "that", "this", "these",
    "those", "from", "into", "about", "can", "could", "should", "would", "does",
    "did", "have", "has", "had", "not", "but", "you", "your", "please", "tell",
    "apakah", "bagaimana", "berapakah", "bilakah", "siapakah", "mengapakah",
    "yang", "dan", "untuk", "atau", "ini", "itu", "dari", "daripada", "dalam",
    "kepada", "pada", "bagi", "adalah", "ialah", "boleh", "perlu", "hendaklah",
    "saya", "kami", "kita", "mereka", "akan", "telah", "sudah", "tidak", "bukan",
}


def expand_query_tokens(query):
    """Expand query tokens deterministically with cross-lingual UUM domain keywords."""
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", query.lower())
    words = [w for w in clean.split() if len(w) > 2 and w not in QUERY_STOPWORDS]
    expanded = []
    seen = set()
    for w in words:
        if w not in seen:
            expanded.append(w)
            seen.add(w)
    for w in words:
        for syn in ENGLISH_TO_MALAY_EXPANSION.get(w, ()):
            for part in syn.split():
                if len(part) > 2 and part not in QUERY_STOPWORDS and part not in seen:
                    expanded.append(part)
                    seen.add(part)
    return expanded


def _extract_reference_codes(query):
    """Extract exact circular/form reference patterns such as '9/2026', '15/2015', 'RMC 008', 'ICC009'."""
    refs = []
    for m in re.finditer(r"\b(?!20\d{2}/20\d{2}\b)\d{1,2}/\d{4}\b", query):
        refs.append(m.group(0).lower())
    for m in re.finditer(r"\b(?:rmc|icc|kew\.pa|ben)\s*-?\s*\d{2,3}\b", query.lower()):
        code = re.sub(r"\s+", " ", m.group(0)).strip()
        refs.append(code)
    return list(dict.fromkeys(refs))


UUM_SCHOOL_PATTERNS: dict[str, re.Pattern[str]] = {
    "soc": re.compile(r"\bsoc\b|school of computing|pusat pengajian pengkomputeran", re.IGNORECASE),
    "smmtc": re.compile(r"\bsmmtc\b|school of multimedia|teknologi multimedia", re.IGNORECASE),
    "sapsp": re.compile(r"\bsapsp\b|applied psychology|psikologi gunaan|pembangunan sosial", re.IGNORECASE),
    "slcp": re.compile(r"\bslcp\b|school of languages|civilisation|pusat bahasa", re.IGNORECASE),
    "soe": re.compile(r"\bsoe\b|school of education|pusat pengajian pendidikan", re.IGNORECASE),
    "sqs": re.compile(r"\bsqs\b|quantitative sciences|sains kuantitatif", re.IGNORECASE),
    "scimpa": re.compile(r"\bscimpa\b|creative industry|industri kreatif", re.IGNORECASE),
    "sbm": re.compile(r"\bsbm\b|school of business management|pengurusan perniagaan", re.IGNORECASE),
    "sefb": re.compile(r"\bsefb\b|economics,\s*finance|ekonomi,\s*kewangan", re.IGNORECASE),
    "stml": re.compile(r"\bstml\b|technology management|pengurusan teknologi", re.IGNORECASE),
    "tissa": re.compile(r"\btissa\b|school of accountancy|perakaunan", re.IGNORECASE),
    "ibs": re.compile(r"\bibs\b|islamic business school|perniagaan islam", re.IGNORECASE),
    "nga": re.compile(r"\bnga\b|\bagn\b|national golf academy|akademi golf", re.IGNORECASE),
    "sol": re.compile(r"\bsol\b|school of law|pusat pengajian undang-undang", re.IGNORECASE),
    "sog": re.compile(r"\bsog\b|school of government|pusat pengajian kerajaan", re.IGNORECASE),
    "sois": re.compile(r"\bsois\b|international studies|pengajian antarabangsa", re.IGNORECASE),
    "sthem": re.compile(r"\bsthem\b|tourism,\s*hospitality|pelancongan", re.IGNORECASE),
}


def _extract_school_targets(query: str) -> set[str]:
    """Return the set of canonical UUM school codes explicitly referenced in a query."""
    targets: set[str] = set()
    for code, pat in UUM_SCHOOL_PATTERNS.items():
        if pat.search(query):
            targets.add(code)
    return targets


def _extract_chunk_schools(chunk: dict[str, Any]) -> set[str]:
    """Return the set of canonical UUM school codes associated with a chunk's metadata."""
    hay = f"{chunk.get('school') or ''} {chunk.get('department') or ''} {chunk.get('circular_ref_no') or ''}"
    matched: set[str] = set()
    for code, pat in UUM_SCHOOL_PATTERNS.items():
        if pat.search(hay):
            matched.add(code)
    return matched


def _extract_session_years(query: str) -> set[str]:
    """Extract normalized academic session tokens (e.g. '2026/2027' -> {'2026/2027', '26 27', '26/27'})."""
    tokens: set[str] = set()
    for m in re.finditer(r"\b20(\d{2})\s*[/\- ]\s*20(\d{2})\b", query):
        y1, y2 = m.group(1), m.group(2)
        tokens.update({f"20{y1}/20{y2}", f"20{y1}-20{y2}", f"20{y1} 20{y2}", f"{y1} {y2}", f"{y1}/{y2}"})
    for m in re.finditer(r"\b(2[0-9])\s*[/\-]\s*(2[1-9])\b", query):
        y1, y2 = m.group(1), m.group(2)
        tokens.update({f"20{y1}/20{y2}", f"20{y1}-20{y2}", f"20{y1} 20{y2}", f"{y1} {y2}", f"{y1}/{y2}"})
    return tokens

_VALID_SHORT_REF_RE = re.compile(
    r"\b(?:\d{1,2}/\d{4}|(?:rmc|icc|kew\.pa|ben|pg)\s*-?\s*\d{2,3}|pekeliling|borang|statut)\b",
    re.IGNORECASE,
)


def _is_junk_chunk(chunk_text: str) -> bool:
    """Detect meaningless form-stub chunks (e.g. ':', 'e.g/cth :', '1 0 2 0 1 0 4') while keeping valid short headers."""
    text = (chunk_text or "").strip()
    if not text:
        return True
    if _VALID_SHORT_REF_RE.search(text):
        return False
    alnum_count = sum(1 for ch in text if ch.isalnum())
    if alnum_count < 15:
        return True
    alpha_words = re.findall(r"[A-Za-z]{3,}", text)
    if len(alpha_words) < 3 and len(text) < 45:
        return True
    return False


def cosine_similarity(v1, v2):
    """Compute cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(v1, v2, strict=False))
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
        self._lock = threading.RLock()
        self._local = threading.local()
        self._generation = 0
        self._vec_cache: dict[str, Any] | None = None

        if self.use_postgres:
            try:
                import psycopg2
                self.pg_con = psycopg2.connect(self.db_url)
            except (ImportError, OSError, RuntimeError) as exc:
                logger.warning(f"PostgreSQL unavailable ({exc}); falling back to SQLite.")
                self.use_postgres = False

        if not self.use_postgres:
            if not os.path.exists(SQLITE_DB):
                raise FileNotFoundError(f"Database not found at {SQLITE_DB}. Please run ingest.py first.")
            self.sqlite_con = self._open_sqlite_connection()
            self._db_mtime = os.path.getmtime(SQLITE_DB)
        else:
            self._db_mtime = 0.0

        self.doc_registry, self.forms_list = self._load_doc_registry()

    def _open_sqlite_connection(self) -> sqlite3.Connection:
        con = sqlite3.connect(SQLITE_DB, timeout=60.0)
        con.row_factory = sqlite3.Row
        return con

    def _get_sqlite_con(self) -> sqlite3.Connection | None:
        """Return a thread-local SQLite connection synced with the current DB generation."""
        if self.use_postgres or not os.path.exists(SQLITE_DB):
            return None
        self._ensure_fresh_sqlite()
        gen = self._generation
        local_con: sqlite3.Connection | None = getattr(self._local, "con", None)
        local_gen: int = getattr(self._local, "gen", -1)
        if local_con is None or local_gen != gen:
            if local_con is not None:
                try:
                    local_con.close()
                except sqlite3.Error as exc:
                    logger.debug(f"Error closing stale thread-local SQLite connection: {exc}")
            local_con = self._open_sqlite_connection()
            self._local.con = local_con
            self._local.gen = gen
        return local_con

    def _reconnect_sqlite(self):
        """Reconnect SQLite and reload registry/vector cache after schema/FTS rebuilds."""
        if self.use_postgres or not os.path.exists(SQLITE_DB):
            return
        with self._lock:
            self._generation += 1
            self._vec_cache = None
            local_con: sqlite3.Connection | None = getattr(self._local, "con", None)
            if local_con is not None:
                try:
                    local_con.close()
                except sqlite3.Error as exc:
                    logger.debug(f"Error closing thread-local SQLite connection: {exc}")
                self._local.con = None
            try:
                if self.sqlite_con:
                    self.sqlite_con.close()
            except sqlite3.Error as exc:
                logger.debug(f"Error closing previous SQLite connection: {exc}")
            self.sqlite_con = self._open_sqlite_connection()
            self._local.con = self.sqlite_con
            self._local.gen = self._generation
            self._db_mtime = os.path.getmtime(SQLITE_DB)
            self.doc_registry, self.forms_list = self._load_doc_registry()

    def _ensure_fresh_sqlite(self):
        """Refresh SQLite connection if the database file was updated on disk."""
        if self.use_postgres or not os.path.exists(SQLITE_DB):
            return
        current_mtime = os.path.getmtime(SQLITE_DB)
        if current_mtime != getattr(self, "_db_mtime", 0.0):
            self._reconnect_sqlite()

    def _load_vector_cache(self) -> dict[str, Any]:
        """Load and L2-normalize all SQLite chunk embeddings into an in-memory NumPy matrix."""
        with self._lock:
            if self._vec_cache is not None and self._vec_cache.get("mtime") == self._db_mtime:
                return self._vec_cache

            con = self._get_sqlite_con()
            if con is None:
                empty: dict[str, Any] = {
                    "mtime": self._db_mtime,
                    "chunk_ids": [],
                    "is_active": np.zeros(0, dtype=bool),
                    "matrix": np.zeros((0, 768), dtype=np.float32),
                    "meta": [],
                    "id_to_idx": {},
                }
                self._vec_cache = empty
                return empty

            cur = con.cursor()
            cur.execute("""
                SELECT chunk_id, circular_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms,
                       doc_type, college, school, academic_level, academic_session, embedding_json
                FROM document_chunks
                WHERE embedding_json IS NOT NULL AND embedding_json != '';
            """)
            chunk_ids: list[str] = []
            is_active_list: list[bool] = []
            meta_list: list[dict[str, Any]] = []
            vec_rows: list[list[float]] = []
            id_to_idx: dict[str, int] = {}
            expected_dim: int | None = None

            for r in cur.fetchall():
                raw_emb = r["embedding_json"]
                if not raw_emb:
                    continue
                try:
                    vec = json.loads(raw_emb)
                except (ValueError, TypeError):
                    continue
                if not isinstance(vec, list) or not vec:
                    continue
                if expected_dim is None:
                    expected_dim = len(vec)
                elif len(vec) != expected_dim:
                    continue

                cid = r["chunk_id"]
                idx = len(chunk_ids)
                chunk_ids.append(cid)
                id_to_idx[cid] = idx
                is_active_list.append(r["status"] == "Active")
                vec_rows.append(vec)
                meta_list.append({
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
                })

            if vec_rows:
                mat = np.asarray(vec_rows, dtype=np.float32)
                norms = np.linalg.norm(mat, axis=1, keepdims=True)
                norms = np.where(norms == 0.0, 1.0, norms)
                mat = mat / norms
            else:
                mat = np.zeros((0, expected_dim or 768), dtype=np.float32)

            cache: dict[str, Any] = {
                "mtime": self._db_mtime,
                "chunk_ids": chunk_ids,
                "is_active": np.asarray(is_active_list, dtype=bool),
                "matrix": mat,
                "meta": meta_list,
                "id_to_idx": id_to_idx,
            }
            self._vec_cache = cache
            return cache

    def _load_doc_registry(self):
        """Build lookup dictionary mapping document/form IDs to file_path, format, and metadata."""
        registry: dict[str, dict[str, Any]] = {}
        forms_list: list[dict[str, Any]] = []
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
        except sqlite3.OperationalError as exc:
            logger.debug(f"circulars table unavailable: {exc}")

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
        except sqlite3.OperationalError as exc:
            logger.debug(f"required_documents_forms table unavailable: {exc}")

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
        except sqlite3.OperationalError as exc:
            logger.debug(f"college_documents table unavailable: {exc}")

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
        except sqlite3.OperationalError as exc:
            logger.debug(f"college_forms table unavailable: {exc}")

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

    def hybrid_search(self, query, top_k=6, filter_active=True, scope="All", semantic_weight=0.4, keyword_weight=0.6):
        """Perform hybrid BM25 + Dense Semantic search across UUM circular & college chunks."""
        self._ensure_fresh_sqlite()
        q_vec = self.ai.get_embedding(query)
        expanded_tokens = expand_query_tokens(query)
        ref_codes = _extract_reference_codes(query)
        fts_query = " OR ".join(expanded_tokens[:16]) if expanded_tokens else ""
        candidates: dict[str, dict[str, Any]] = {}

        if self.use_postgres and self.pg_con is not None:
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
                    if _is_junk_chunk(row[7]):
                        continue
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
                    if _is_junk_chunk(row[7]):
                        continue
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
            sqlite_con = self._get_sqlite_con()
            if sqlite_con is not None:
                vec_cache = self._load_vector_cache()
                mat = vec_cache["matrix"]
                id_to_idx = vec_cache["id_to_idx"]

                q_arr = np.asarray(q_vec, dtype=np.float32) if q_vec else np.zeros(0, dtype=np.float32)
                q_norm = float(np.linalg.norm(q_arr)) if q_arr.size else 0.0
                q_unit = (q_arr / q_norm) if q_norm > 0.0 else q_arr
                has_valid_vec = bool(mat.shape[0] > 0 and q_unit.size == mat.shape[1] and q_norm > 0.0)

                def _cached_sim(chunk_id: str) -> float:
                    if not has_valid_vec:
                        return 0.0
                    idx = id_to_idx.get(chunk_id)
                    if idx is None:
                        return 0.0
                    return float(np.dot(mat[idx], q_unit))

                # 1. SQLite FTS5 Search (with expanded tokens & junk-stub filtering)
                is_all_scope = not scope or scope.lower() in ("all", "all uum")
                fts_limit = 220 if is_all_scope else 650
                fts_target = max(60, top_k * 4)
                if fts_query:
                    for attempt in range(2):
                        try:
                            cur = sqlite_con.cursor()
                            cur.execute("""
                                SELECT c.chunk_id, c.circular_id, c.circular_ref_no, c.department, c.status, c.section_heading, c.page_number, c.chunk_text, c.required_forms,
                                       c.doc_type, c.college, c.school, c.academic_level, c.academic_session,
                                       rank AS bm25_rank
                                FROM chunks_fts f
                                JOIN document_chunks c ON f.chunk_id = c.chunk_id
                                WHERE chunks_fts MATCH ? AND (? = 0 OR c.status = 'Active')
                                ORDER BY rank LIMIT ?;
                            """, (fts_query, 1 if filter_active else 0, fts_limit))
                            for r in cur.fetchall():
                                if _is_junk_chunk(r["chunk_text"]):
                                    continue
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
                                item["bm25_score"] = abs(float(r["bm25_rank"]))
                                item["vec_score"] = _cached_sim(cid)
                                candidates[cid] = item
                                if len(candidates) >= fts_target:
                                    break
                            break
                        except sqlite3.Error as exc:
                            logger.warning(f"SQLite FTS5 query error (attempt {attempt + 1}): {exc}")
                            if attempt == 0:
                                self._reconnect_sqlite()
                                sqlite_con = self._get_sqlite_con()
                                if sqlite_con is None:
                                    break
                            else:
                                break

                # 2. Vectorized NumPy semantic search across cached embeddings
                min_sim = 0.38 if (expanded_tokens or ref_codes) else 0.62
                if has_valid_vec:
                    sims = mat @ q_unit
                    mask = sims > min_sim
                    if filter_active:
                        mask = mask & vec_cache["is_active"]
                    hit_indices = np.flatnonzero(mask)
                    if hit_indices.size > 0:
                        order = hit_indices[np.argsort(sims[hit_indices])[::-1]]
                        vec_target = max(35, top_k * 3)
                        added_vec = 0
                        meta_list = vec_cache["meta"]
                        for idx in order:
                            meta = meta_list[int(idx)]
                            cid = meta["chunk_id"]
                            if cid in candidates:
                                continue
                            if _is_junk_chunk(meta["chunk_text"]):
                                continue
                            if not self._match_Scope(meta, scope):
                                continue
                            item = dict(meta)
                            item["bm25_score"] = 0.0
                            item["vec_score"] = float(sims[int(idx)])
                            candidates[cid] = item
                            added_vec += 1
                            if added_vec >= vec_target:
                                break

                # 3. Exact circular/form reference injection (e.g. '9/2026', '15/2015', 'RMC 008')
                if ref_codes and sqlite_con is not None:
                    cur = sqlite_con.cursor()
                    for ref in ref_codes:
                        like_pat = f"%{ref}%"
                        cur.execute("""
                            SELECT chunk_id, circular_id, circular_ref_no, department, status, section_heading, page_number, chunk_text, required_forms,
                                   doc_type, college, school, academic_level, academic_session
                            FROM document_chunks
                            WHERE (? = 0 OR status = 'Active')
                              AND (lower(COALESCE(circular_ref_no, '')) LIKE ?
                                   OR lower(COALESCE(required_forms, '')) LIKE ?
                                   OR lower(chunk_text) LIKE ?)
                            LIMIT 25;
                        """, (1 if filter_active else 0, like_pat, like_pat, like_pat))
                        for r in cur.fetchall():
                            if _is_junk_chunk(r["chunk_text"]):
                                continue
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
                            if cid not in candidates:
                                item["bm25_score"] = 1.0
                                item["vec_score"] = _cached_sim(cid)
                                candidates[cid] = item
                            candidates[cid]["exact_ref_hit"] = True

        asks_for_form = bool(re.search(r"\b(which form|what form|borang apa|apakah borang|senarai borang)\b", query.lower()))
        target_schools = _extract_school_targets(query)
        target_sessions = _extract_session_years(query)
        results = list(candidates.values())
        max_bm25 = max([c["bm25_score"] for c in results], default=1.0) or 1.0
        for c in results:
            base_score = (semantic_weight * c["vec_score"]) + (keyword_weight * (c["bm25_score"] / max_bm25))
            if c.get("exact_ref_hit"):
                base_score = min(1.0, base_score + 0.35)
            if asks_for_form and c.get("doc_type") in ("college_form", "admin_form"):
                base_score = min(1.0, base_score + 0.12)

            if target_schools:
                chunk_schools = _extract_chunk_schools(c)
                if chunk_schools & target_schools:
                    base_score = min(1.0, base_score + 0.22)
                    c["school_match"] = True
                elif chunk_schools:
                    base_score = max(0.0, base_score - 0.22)
                    c["school_mismatch"] = True

            if target_sessions:
                sess_hay = f"{c.get('academic_session') or ''} {c.get('circular_ref_no') or ''}".lower()
                if any(tok in sess_hay for tok in target_sessions):
                    base_score = min(1.0, base_score + 0.12)

            c["combined_score"] = round(base_score, 4)

        results.sort(key=lambda x: x["combined_score"], reverse=True)

        # When specific target_schools are requested, prioritize non-mismatched chunks first
        if target_schools:
            matched_or_neutral = [c for c in results if not c.get("school_mismatch")]
            mismatched = [c for c in results if c.get("school_mismatch")]
            results = matched_or_neutral + mismatched

        # Per-document diversity cap over expanded candidate pool
        pool = results[:max(top_k * 4, 24)]
        selected: list[dict[str, Any]] = []
        overflow: list[dict[str, Any]] = []
        doc_counts: dict[str, int] = {}
        # Allow up to 3 chunks per doc when a single school is targeted and fewer than 3 matching docs exist
        matching_doc_ids = {c.get("circular_id") for c in pool if c.get("school_match")}
        max_per_doc = 3 if (len(target_schools) == 1 and 0 < len(matching_doc_ids) < 3) else 2
        for c in pool:
            if target_schools and c.get("school_mismatch") and len(selected) >= len(matching_doc_ids) and len(selected) > 0:
                overflow.append(c)
                continue
            doc_key = c.get("circular_id") or c.get("chunk_id") or ""
            if doc_counts.get(doc_key, 0) < max_per_doc:
                selected.append(c)
                doc_counts[doc_key] = doc_counts.get(doc_key, 0) + 1
                if len(selected) >= top_k:
                    break
            else:
                overflow.append(c)

        if len(selected) < top_k and overflow:
            selected.extend(overflow[: top_k - len(selected)])

        for c in selected:
            self._enrich_chunk(c)
        return selected

    def get_document_preview(self, doc_id):
        """Return full metadata and extracted sections/clauses for any document or form ID."""
        self._ensure_fresh_sqlite()
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
        sqlite_con = self._get_sqlite_con()
        if sqlite_con is not None:
            cur = sqlite_con.cursor()
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
                except (OSError, ValueError) as exc:
                    logger.warning(f"On-demand preview extraction failed for {doc_id}: {exc}")

        return {
            "meta": meta,
            "sections": sections,
        }

    def _generate_follow_up_questions(self, query, retrieved, all_forms):
        """Build up to 3 grounded follow-up questions in the user's query language."""
        is_en = is_english_query(query)
        q_lower = query.strip().lower()
        suggestions = []

        def _add(text):
            clean = " ".join(text.split())
            if clean and clean.lower() != q_lower and clean not in suggestions:
                suggestions.append(clean)

        # 1. Form-focused follow-up if linked or retrieved forms exist
        form_target = None
        if all_forms:
            form_target = all_forms[0]
        else:
            for src in retrieved:
                if src.get("doc_type") in ("college_form", "admin_form"):
                    form_target = src
                    break

        if form_target:
            ftitle = (form_target.get("title") or form_target.get("code") or "").strip()
            if ftitle:
                if is_en:
                    _add(f"What signatures, approvals, and supporting documents are needed for {ftitle}?")
                else:
                    _add(f"Apakah tandatangan, kelulusan, dan dokumen sokongan yang diperlukan bagi {ftitle}?")

        # 2. Deep-dive on primary retrieved document
        if retrieved:
            top = retrieved[0]
            top_title = (top.get("title") or top.get("circular_ref_no") or "").strip()
            if top_title:
                if is_en:
                    _add(f"What are the eligibility criteria, rates, or deadlines under {top_title}?")
                else:
                    _add(f"Apakah syarat kelayakan, kadar, atau tempoh masa di bawah {top_title}?")

        # 3. Secondary distinct document follow-up
        seen_titles = {(retrieved[0].get("title") or "").strip().lower()} if retrieved else set()
        for src in retrieved[1:]:
            stitle = (src.get("title") or src.get("circular_ref_no") or "").strip()
            if stitle and stitle.lower() not in seen_titles:
                seen_titles.add(stitle.lower())
                if is_en:
                    _add(f"What procedures or forms are required in {stitle}?")
                else:
                    _add(f"Apakah prosedur atau borang yang berkaitan dalam {stitle}?")
                break

        # 4. Fallback scope-level follow-up so users always see helpful next questions
        if len(suggestions) < 3:
            if is_en:
                _add("Which official UUM forms or checklists apply to this procedure?")
                _add("Are there any latest amendments or active circulars related to this topic?")
            else:
                _add("Apakah borang rasmi atau senarai semak UUM yang berkaitan dengan urusan ini?")
                _add("Adakah terdapat pindaan terkini atau pekeliling aktif yang berkaitan?")

        return suggestions[:3]

    def ask(self, query, filter_active=True, scope="All", top_k=6, previous_query=""):
        """Ask question and generate grounded response with strict citations and linked files."""
        is_en = is_english_query(query)
        lang = "en" if is_en else "ms"
        search_query = query
        if previous_query and previous_query.strip() and previous_query.strip().lower() != query.strip().lower():
            if len(query.split()) <= 12 or re.search(r"\b(this|that|these|those|it|ini|itu|tersebut)\b", query.lower()):
                search_query = f"{query} {previous_query.strip()}"

        retrieved = self.hybrid_search(search_query, top_k=top_k, filter_active=filter_active, scope=scope)

        if not retrieved:
            if is_en:
                msg = "No official circulars, academic handbooks, or forms were found matching your query and scope filter. Try broadening your scope to 'All UUM' or contact the responsible PTJ / College."
            else:
                msg = "Tiada pekeliling, buku panduan akademik, atau borang rasmi yang ditemui bagi carian dan tapisan ini. Sila cuba tapisan 'All UUM' atau hubungi PTJ / Kolej berkenaan."
            return {
                "answer": msg,
                "provider": "None",
                "sources": [],
                "linked_forms": [],
                "follow_up_questions": [],
                "query": query,
                "scope": scope,
                "language": lang,
            }

        response_text, provider_name = self.ai.generate_chat_response(query, retrieved)

        # Deduplicate linked forms using a relative relevance floor tied to the top-ranked chunk
        top_score = float(retrieved[0].get("combined_score", 0.0))
        form_floor = top_score * 0.65
        direct_form_floor = top_score * 0.55

        all_forms = []
        seen_fids = set()
        for s in retrieved:
            score = float(s.get("combined_score", 0.0))
            is_form_doc = s.get("doc_type") in ("admin_form", "college_form")
            if score < form_floor and not (is_form_doc and score >= direct_form_floor):
                continue
            for fm in s.get("linked_forms", []):
                if fm["doc_id"] not in seen_fids:
                    all_forms.append(fm)
                    seen_fids.add(fm["doc_id"])
                    if len(all_forms) >= 6:
                        break
            if len(all_forms) >= 6:
                break

        follow_ups = self._generate_follow_up_questions(query, retrieved, all_forms)

        return {
            "answer": response_text,
            "provider": provider_name,
            "sources": retrieved,
            "linked_forms": all_forms,
            "follow_up_questions": follow_ups,
            "query": query,
            "scope": scope,
            "language": lang,
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

