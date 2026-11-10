#!/usr/bin/env python3
"""
UUM College Documents Master Tracker Generator
Scans the standardized `circular_forms/College_documents/` hierarchy and builds
`college_documents_tracker.xlsx` with two tailored sheets:
  1. `college_docs`  — Academic Calendars, Handbooks, Programmes, Guidelines & Rubrics
  2. `college_forms` — Practicum, Staff & Student Forms across CAS, COB, COLGIS & HEA

Usage:
    python3 src/college_tracker.py [--output college_documents_tracker.xlsx]
"""

import os
import re
import sys
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.tracker_sorter import ExcelWriter, find_root_dir

BASE_DIR = find_root_dir()
COLLEGE_DIR = os.path.join(BASE_DIR, "circular_forms", "College_documents")
DEFAULT_OUT = os.path.join(BASE_DIR, "college_documents_tracker.xlsx")

COLLEGE_LABELS = {
    "00_university_shared": ("UNI", "University Shared (HEA / CUIC)"),
    "cas": ("CAS", "UUM CAS (College of Arts & Sciences)"),
    "cob": ("COB", "UUM COB (College of Business)"),
    "colgis": ("CLG", "UUM COLGIS (Law, Government & International Studies)"),
}

SCHOOL_LABELS = {
    # Shared
    "shared": "HEA / CUIC (University-Wide)",
    # CAS
    "central_cas": "Central CAS / AHSGS",
    "sapsp": "SAPSP — School of Applied Psychology, Social Work & Policy",
    "scimpa": "SCIMPA — School of Creative Industry Management & Performing Arts",
    "slcp": "SLCP — School of Languages, Civilisation & Philosophy",
    "smmtc": "SMMTC — School of Multimedia Technology & Communication",
    "soc": "SOC — School of Computing",
    "soe": "SOE — School of Education",
    "sqs": "SQS — School of Quantitative Sciences",
    # COB
    "central_cob": "Central COB",
    "ibs": "IBS — Islamic Business School",
    "nga": "NGA — National Golf Academy (AGN)",
    "sbm": "SBM — School of Business Management",
    "sefb": "SEFB — School of Economics, Finance & Banking",
    "stml": "STML — School of Technology Management & Logistics",
    "tissa": "TISSA — Tunku Puteri Intan Safinaz School of Accountancy",
    # COLGIS
    "central_colgis": "Central COLGIS / GSGSG",
    "sog": "SOG — School of Government",
    "sois": "SOIS — School of International Studies",
    "sol": "SOL — School of Law",
    "sthem": "STHEM — School of Tourism, Hospitality & Event Management",
}

CATEGORY_LABELS = {
    "01_academic_calendars": "Academic Calendar",
    "02_academic_handbooks": "Academic Handbook",
    "03_academic_programmes": "Academic Programme",
    "05_guidelines_and_rubrics": "Guideline & Rubric",
}

FORM_CATEGORY_LABELS = {
    "practicum_training_forms": "Practicum & Industrial Training",
    "staff_forms": "Staff & Academic Admin",
    "student_forms": "Student Academic & Thesis",
}


def extract_session_info(filename):
    """Extract normalized academic session (e.g. '2026/2027') and numeric sort year."""
    stem = os.path.splitext(filename)[0]

    # Explicit 4-digit session range: 2025_2026, 2025 - 2026, 2021-2022, 2015_2016
    m4 = re.search(r"(20[12]\d)\s*[-_ ]\s*(20[12]\d)", stem)
    if m4:
        y1, y2 = sorted([int(m4.group(1)), int(m4.group(2))])
        return f"{y1}/{y2}", y1

    # UUM semester codes: A261, A251, A252, A241, A242, A202, A191, A192, A172, 261-262, SAPSP 251
    m_sem = re.search(r"(?:^|[^0-9])A?(1[7-9]|2[0-7])[12](?:[^0-9]|$)", stem, re.IGNORECASE)
    if m_sem:
        yr = 2000 + int(m_sem.group(1))
        return f"{yr}/{yr + 1}", yr

    # 2-digit academic year pairs: 26_27, 25_26, 24_23 (reversed), 26_25 (reversed), 19_20
    for m2 in re.finditer(r"(?:^|[^0-9])(1[7-9]|2[0-7])[-_ ](1[7-9]|2[0-7])(?:[^0-9]|$)", stem):
        a, b = int(m2.group(1)), int(m2.group(2))
        if abs(a - b) == 1:
            y1 = 2000 + min(a, b)
            return f"{y1}/{y1 + 1}", y1

    # Standalone 4-digit year: 2016..2027
    m_yr = re.search(r"(201[5-9]|202[0-7])", stem)
    if m_yr:
        yr = int(m_yr.group(1))
        return str(yr), yr

    return "Current", 2026


def clean_readable_title(filename):
    """Produce a clean human-readable document/form title from filename."""
    stem = os.path.splitext(filename)[0]
    # Fix known typo in original filename for display title while keeping File_Path exact
    stem = re.sub(r"hanbdooks", "Handbooks", stem, flags=re.IGNORECASE)
    stem = re.sub(r"gudelines", "Guidelines", stem, flags=re.IGNORECASE)
    stem = re.sub(r"^Copy of\s+", "", stem, flags=re.IGNORECASE)
    stem = stem.replace("_", " ").replace("  ", " ").strip()
    stem = re.sub(r"\s{2,}", " ", stem)
    if (stem.isupper() or stem.islower()) and len(stem) > 8:
        stem = stem.title()
        for acr in (
            "UUM", "CAS", "COB", "COLGIS", "HEA", "CUIC", "AHSGS", "GSGSG",
            "SAPSP", "SCIMPA", "SLCP", "SMMTC", "SOC", "SOE", "SQS",
            "IBS", "NGA", "AGN", "SBM", "SEFB", "STML", "TISSA",
            "SOG", "SOIS", "SOL", "STHEM", "ETD", "OBE", "PEO", "PLO",
        ):
            stem = re.sub(rf"\b{acr.title()}\b", acr, stem)
    return stem


def infer_form_code(filename, school_key, form_sub):
    """Extract official UUM form code if present, else generate a clean structured code."""
    low = filename.lower()
    patterns = [
        (r"\b(pg\d{4})\b", lambda m: m.group(1).upper()),
        (r"\b(pli-\d{2})\b", lambda m: m.group(1).upper()),
        (r"\b(prak0[12](?:-obe)?)\b", lambda m: m.group(1).upper()),
        (r"\b(it0[12])\b", lambda m: m.group(1).upper()),
        (r"\b(c03a)\b", lambda m: m.group(1).upper()),
        (r"\b(i-form)\b", lambda _: "I-FORM"),
        (r"\b(loc3d)\b", lambda _: "LOC3D"),
        (r"\b(ap[12])up", lambda m: m.group(1).upper()),
        (r"sep\s*form\s*\((inbound|outbound)\)", lambda m: f"SEP-{m.group(1)[:3].upper()}"),
        (r"hea-?\s*_?borang\s+([a-z_ ]+?)[-_ ]new", lambda m: "HEA-" + m.group(1).strip().replace(" ", "-").upper()[:12]),
        (r"etd[_ ]form|permission[_ ]to[_ ]deposit.*etd", lambda _: "UUM-ETD"),
    ]
    for pat, fmt in patterns:
        m = re.search(pat, low)
        if m:
            return fmt(m)

    prefix = "UNI" if school_key == "shared" else school_key.replace("central_", "").upper()
    sub_tag = "PRK" if "practicum" in form_sub else ("STF" if "staff" in form_sub else "STD")
    short = re.sub(r"[^A-Za-z0-9]+", "-", os.path.splitext(filename)[0]).strip("-").upper()[:10]
    return f"{prefix}-{sub_tag}-{short}"


def infer_academic_level(rel_parts, filename):
    """Determine Undergraduate, Postgraduate, or General / All Levels."""
    joined = "/".join(rel_parts).lower()
    low_fn = filename.lower()
    if "postgraduate" in joined or any(
        k in low_fn
        for k in (
            "phd", "master", "msc", "mibs", "mifb", "mhrm", "mcim", "ed.d",
            "postgraduate", "pg handbook", "pgdhelt", "thesis", "tesis", "viva",
            "dissertation", "disertasi", "proposal", "kertas cadangan",
            "colloquium", "ahsgs", "gsgsg", "bpmz", "sccz6996",
            "smjz69912", "smmz69912", "sgdz6996", "mpm_registration",
            "pg001", "oral_examination", "oral_defense",
        )
    ):
        return "Postgraduate"
    if "undergraduate" in joined or any(
        k in low_fn
        for k in (
            "bachelor", "sarjana muda", "undergrad", "ug ", "practicum",
            "praktikum", "industrial training", "industrial-training", "latihan ilmiah",
            "latihan_ilmiah", "minor", "elektif", "adddrop", "gugur_tambah",
            "double_degree", "biam", "bibm", "bhalal", "bifb", "bma",
        )
    ):
        return "Undergraduate"
    return "General / All Levels"


def infer_target_user(form_sub, level):
    if form_sub == "staff_forms":
        return "Academic / Admin Staff"
    if form_sub == "practicum_training_forms":
        return "Student / Employer (Practicum)"
    if level == "Postgraduate":
        return "Student (Postgraduate)"
    if level == "Undergraduate":
        return "Student (Undergraduate)"
    return "Student (General)"


def scan_college_documents():
    docs = []
    forms = []

    for root, dirs, files in os.walk(COLLEGE_DIR):
        dirs.sort()
        for fn in sorted(files):
            if fn == "COLLECTION_NOTES.md" or fn.startswith(".") or ":Zone.Identifier" in fn:
                continue
            abs_fp = os.path.join(root, fn)
            rel_cd = os.path.relpath(abs_fp, COLLEGE_DIR).replace("\\", "/")
            rel_repo = os.path.relpath(abs_fp, BASE_DIR).replace("\\", "/")
            parts = rel_cd.split("/")

            top_college = parts[0]
            col_code, col_label = COLLEGE_LABELS[top_college]
            cat_folder = parts[1]
            ext = os.path.splitext(fn)[1].lower().lstrip(".").upper() or "FILE"
            title = clean_readable_title(fn)
            session_str, sort_yr = extract_session_info(fn)
            level = infer_academic_level(parts, fn)

            if top_college == "00_university_shared":
                school_key = "shared"
            else:
                # Category layouts:
                # 02_academic_handbooks/<school>/<fn>
                # 03_academic_programmes/<level>/<school>/<fn>
                # 04_forms/<form_sub>/<school>/<fn>
                # 05_guidelines_and_rubrics/<school>/<fn>
                school_key = parts[-2]

            school_label = SCHOOL_LABELS.get(school_key, school_key.upper())

            if cat_folder == "04_forms":
                form_sub = parts[2]
                forms.append({
                    "col_code": col_code,
                    "form_code": infer_form_code(fn, school_key, form_sub),
                    "title": title,
                    "college": col_label,
                    "school_key": school_key,
                    "school": school_label,
                    "form_category": FORM_CATEGORY_LABELS.get(form_sub, form_sub),
                    "target_user": infer_target_user(form_sub, level),
                    "session": session_str,
                    "format": ext,
                    "filepath": rel_repo,
                })
            else:
                # Academic handbooks: infer Undergraduate unless shared PG handbook
                if cat_folder == "02_academic_handbooks" and top_college != "00_university_shared":
                    level = "Undergraduate"
                docs.append({
                    "col_code": col_code,
                    "title": title,
                    "college": col_label,
                    "school_key": school_key,
                    "school": school_label,
                    "category": CATEGORY_LABELS.get(cat_folder, cat_folder),
                    "cat_folder": cat_folder,
                    "level": level,
                    "session": session_str,
                    "sort_yr": sort_yr,
                    "status": "Active",
                    "format": ext,
                    "filepath": rel_repo,
                })

    # Determine Active vs Archive for multi-year Academic Handbooks per (college, school, level)
    max_hb_yr = {}
    for d in docs:
        if d["cat_folder"] == "02_academic_handbooks" and d["session"] != "Current":
            key = (d["college"], d["school_key"], d["level"])
            max_hb_yr[key] = max(max_hb_yr.get(key, 0), d["sort_yr"])

    for d in docs:
        if d["cat_folder"] == "02_academic_handbooks" and d["session"] != "Current":
            key = (d["college"], d["school_key"], d["level"])
            if d["sort_yr"] < max_hb_yr.get(key, 0) or d["sort_yr"] < 2024:
                d["status"] = "Archive"

    # Sort docs cleanly: College -> Category -> School -> Status (Active first) -> Year DESC -> Title
    docs.sort(key=lambda d: (
        d["college"],
        d["category"],
        d["school"],
        0 if d["status"] == "Active" else 1,
        -d["sort_yr"],
        d["title"],
    ))
    col_counters = {}
    for d in docs:
        cc = d["col_code"]
        col_counters[cc] = col_counters.get(cc, 0) + 1
        d["id"] = f"CDOC-{cc}-{col_counters[cc]:03d}"

    # Sort forms cleanly: College -> School -> Form Category -> Target User -> Title
    forms.sort(key=lambda f: (
        f["college"],
        f["school"],
        f["form_category"],
        f["target_user"],
        f["title"],
    ))
    f_counters = {}
    for f in forms:
        cc = f["col_code"]
        f_counters[cc] = f_counters.get(cc, 0) + 1
        f["id"] = f"CFORM-{cc}-{f_counters[cc]:03d}"

    return docs, forms


def main():
    parser = argparse.ArgumentParser(description="Generate UUM College Documents Master Excel Tracker")
    parser.add_argument("--output", default=DEFAULT_OUT, help="Output path for college_documents_tracker.xlsx")
    args = parser.parse_args()

    docs, forms = scan_college_documents()

    doc_headers = [
        "Doc_ID",
        "Title",
        "College",
        "School",
        "Category",
        "Academic_Level",
        "Academic_Session",
        "Status",
        "File_Format",
        "File_Path",
    ]
    doc_rows = [
        [
            d["id"],
            d["title"],
            d["college"],
            d["school"],
            d["category"],
            d["level"],
            d["session"],
            d["status"],
            d["format"],
            d["filepath"],
        ]
        for d in docs
    ]

    form_headers = [
        "Form_ID",
        "Form_Code",
        "Form_Title",
        "College",
        "School",
        "Form_Category",
        "Target_User",
        "Academic_Session",
        "File_Format",
        "File_Path",
    ]
    form_rows = [
        [
            f["id"],
            f["form_code"],
            f["title"],
            f["college"],
            f["school"],
            f["form_category"],
            f["target_user"],
            f["session"],
            f["format"],
            f["filepath"],
        ]
        for f in forms
    ]

    ExcelWriter.write_workbook(
        args.output,
        "college_docs",
        doc_headers,
        doc_rows,
        "college_forms",
        form_headers,
        form_rows,
    )

    active_docs = sum(1 for d in docs if d["status"] == "Active")
    archive_docs = len(docs) - active_docs

    print("=" * 72)
    print("  UUM COLLEGE DOCUMENTS MASTER TRACKER GENERATED")
    print("=" * 72)
    print(f"  • Output File   : {args.output}")
    print(f"  • Sheet 1       : college_docs  ({len(docs)} rows — {active_docs} Active, {archive_docs} Archive)")
    print(f"  • Sheet 2       : college_forms ({len(forms)} rows)")
    print(f"  • Total Catalog : {len(docs) + len(forms)} standardized files")
    print("=" * 72)


if __name__ == "__main__":
    main()
