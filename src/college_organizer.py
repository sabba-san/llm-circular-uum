#!/usr/bin/env python3
"""
UUM College Documents Organizer & Standardizer
Audits, deduplicates (by SHA-256), cleans Windows/Office temp artifacts,
consolidates collection notes (ps.txt), and reorganizes `circular_forms/College_documents/`
into a clean, collision-free standardized hierarchy.

Usage:
    python3 src/college_organizer.py --dry-run
    python3 src/college_organizer.py
"""

import os
import re
import json
import shutil
import hashlib
import argparse
import collections

def find_root_dir():
    curr = os.path.dirname(os.path.abspath(__file__))
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "circular_forms")) or os.path.exists(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

BASE_DIR = find_root_dir()
CIRCULAR_FORMS_DIR = os.path.join(BASE_DIR, "circular_forms")
COLLEGE_DIR = os.path.join(CIRCULAR_FORMS_DIR, "College_documents")
MANIFEST_PATH = os.path.join(BASE_DIR, "data", "college_reorg_manifest.json")
NOTES_FILENAME = "COLLECTION_NOTES.md"

SCHOOL_CODES = {
    # CAS
    "central_cas", "sapsp", "scimpa", "slcp", "smmtc", "soc", "soe", "sqs",
    # COB
    "central_cob", "ibs", "nga", "sbm", "sefb", "stml", "tissa", "soa",
    # COLGIS
    "central_colgis", "sog", "sois", "sol", "sthem",
}

GUIDELINE_KEYWORDS = [
    "guideline",
    "gudelines",
    "guidebook",
    "guidebcom",
    "guidetm",
    "prev_guide",
    "user guide",
    "academic-research-paper-handbook",
    "incomplete_grade_application_guide",
    "format_laporan_pratikum",
    "panduan",
    "rubric",
    "flow_chart",
    "process_flow",
    "carta alir",
    "proses kerja",
    "marking_criteria",
    "grading_confirmation_procedure",
    "peraturanpengijazahan",
    "graduationn_rules",
    "kriteria_pindahkredit",
    "faq-",
    "important-dates",
    "journal_list",
    "lampiran a - teras",
    "lampiran b_minor",
    "lampiran_1_peo",
    "_peo.pdf",
    "_plo.pdf",
    "turnitin_1.pdf",
    "jumlah_responden_pp_",
]

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def is_temp_artifact(filename):
    return (
        ":Zone.Identifier" in filename
        or filename.lower() == "desktop.ini"
        or "~$" in filename
    )

def clean_canonical_rank(rel_path):
    """Score candidate paths in a duplicate group; lower score = cleaner canonical filename."""
    fn = os.path.basename(rel_path)
    low = fn.lower()
    has_paren_num = 1 if re.search(r"\(\d+\)", fn) else 0
    has_trailing_one = 1 if re.search(r"_1\.[a-z0-9]+$", low) else 0
    is_all_upper = 1 if fn.isupper() else 0
    return (has_paren_num, has_trailing_one, is_all_upper, len(fn), rel_path)

def classify_document(rel_path, all_rel_set):
    """
    Map a relative path inside `College_documents/` to its standardized target relative path.
    """
    norm_rel = rel_path.replace("\\", "/")
    parts = norm_rel.split("/")
    filename = parts[-1]
    low_fn = filename.lower()
    dir_rel = "/".join(parts[:-1])
    low_dir = dir_rel.lower()

    # 1. Targeted filename repairs verified by content inspection
    target_fn = filename
    if norm_rel == "colgis/sog/forms/undergrad_form/handbooks_dev_mng_degree.pdf":
        # Verified 1-page PDF: SESI A241 BORANG GUGUR/TAMBAH KURSUS (ADD/DROP FORM)
        return "colgis/04_forms/student_forms/sog/SOG_Borang_Gugur_Tambah_Kursus_A241.pdf"

    if target_fn.endswith(".pdf.crdownload.pdf"):
        target_fn = target_fn.replace(".pdf.crdownload.pdf", ".pdf")

    # Handle STML 2-page image brochure pairs: Foo.<ext> + Foo (2).<ext>
    if "cob/stml/" in low_dir and low_fn.endswith((".jpg", ".png")):
        m_p2 = re.match(r"^(.+?)\s*\(2\)(\.[a-zA-Z0-9]+)$", target_fn)
        if m_p2:
            target_fn = f"{m_p2.group(1)}_Page2{m_p2.group(2)}"
        else:
            stem, ext = os.path.splitext(target_fn)
            counterpart = f"{dir_rel}/{stem} (2){ext}"
            if counterpart in all_rel_set:
                target_fn = f"{stem}_Page1{ext}"

    # 2. University-Wide Shared Documents (00_university_shared/)
    if parts[0] == "00_university_shared":
        return norm_rel

    if parts[0] == "academic_calender":
        level = "postgraduate" if "postgrad" in low_dir else "undergraduate"
        return f"00_university_shared/01_academic_calendars/{level}/{target_fn}"

    if parts[0] == "college_shared_same":
        level = "postgraduate" if "postgrad" in low_dir else "undergraduate"
        return f"00_university_shared/02_academic_handbooks/{level}/{target_fn}"

    # University-wide HEA / CUIC / Pendaftar shared forms & guidelines
    if low_fn in (
        "hea- borang elektif bebas- new form- bi_.docx",
        "hea- borang pertukaran minor- new form- bi_.docx",
        "hea-_borang_pendaftaran_minor-_new_form-_bi.png",
    ):
        return f"00_university_shared/04_forms/student_forms/{target_fn}"

    if low_fn in ("attendance form.pdf", "attendance_form.pdf", "attendance-form.pdf"):
        return "00_university_shared/04_forms/practicum_training_forms/Attendance_Form.pdf"

    if low_fn in ("i-form-english-version.pdf", "i-form.pdf"):
        return "00_university_shared/04_forms/practicum_training_forms/I-FORM-English-Version.pdf"

    if low_fn == "7_borang_keluar_waktu_pejabat.pdf":
        return "00_university_shared/04_forms/staff_forms/7_borang_keluar_waktu_pejabat.pdf"

    if low_fn in ("practicum guidelines for employer.pdf", "practicum-guidelines-for-employer-.pdf"):
        return "00_university_shared/05_guidelines_and_rubrics/PRACTICUM GUIDELINES FOR EMPLOYER.pdf"

    # 3. Special Cross-School / Archive Overrides
    if norm_rel == "cas/sapsp/academic_handbooks/undergraduate_handbook/SOE(2020).pdf":
        return "cas/02_academic_handbooks/soe/SOE(2020).pdf"

    if low_fn == "panduan_akademik_sesi_2015_2016_cas.zip":
        return f"cas/02_academic_handbooks/central_cas/{target_fn}"

    # 4. Identify College & School
    college = parts[0].lower()
    if college not in ("cas", "cob", "colgis"):
        raise ValueError(f"Unexpected top-level directory in College_documents: {rel_path}")

    school = None
    for seg in parts[1:-1]:
        s_low = seg.lower()
        if s_low in SCHOOL_CODES:
            school = "tissa" if s_low == "soa" else s_low
            break

    if school is None:
        if norm_rel.startswith("cas/03_academic_programmes/"):
            school = "scimpa"
        elif norm_rel.startswith("cob/03_academic_programmes/"):
            school = "sefb"
        elif norm_rel.startswith("cob/04_forms/practicum_training_forms/"):
            school = "sefb"
        else:
            school = f"central_{college}"

    # 5. Route into 02_academic_handbooks, 03_academic_programmes, 04_forms, or 05_guidelines_and_rubrics
    # 5a. Academic Handbooks
    if (
        "02_academic_handbooks" in low_dir
        or "academic_handbooks" in low_dir
        or norm_rel == "colgis/sog/undergrad_program/handbooks_dev_mng_degree.pdf"
    ):
        return f"{college}/02_academic_handbooks/{school}/{target_fn}"

    # 5b. Guidelines, Rubrics, Flowcharts & Reference Guides
    is_guideline = (
        "05_guidelines_and_rubrics" in low_dir
        or "/other_docs" in low_dir
        or "/rubric" in low_dir
        or "/thesis_guideline" in low_dir
        or any(kw in low_fn for kw in GUIDELINE_KEYWORDS)
    )
    if is_guideline:
        return f"{college}/05_guidelines_and_rubrics/{school}/{target_fn}"

    # 5c. Academic Programmes (Undergraduate vs Postgraduate)
    if any(
        seg in low_dir
        for seg in (
            "03_academic_programmes",
            "undergrad_program",
            "undergrad_programmes",
            "postgrad_program",
            "postgrad_programmes",
        )
    ):
        level = "postgraduate" if "postgrad" in low_dir else "undergraduate"
        return f"{college}/03_academic_programmes/{level}/{school}/{target_fn}"

    # 5d. Forms (Practicum vs Staff vs Student)
    if (
        "practicum_training_forms" in low_dir
        or "practicum_form" in low_dir
        or "undergrad_files_praticum" in low_dir
        or ("industrial_training_practicum_docs" in low_dir and "misc_doc" not in low_dir)
    ):
        form_sub = "practicum_training_forms"
    elif (
        "staff_form" in low_dir
        or "/staff/" in low_dir
        or "/forms/admin" in low_dir
        or ("/forms/academic" in low_dir and low_fn != "sapsp_academic_exercise.pdf")
        or "borang_permohonan_jawatan_akademik" in low_dir
        or "kebajikan_staf" in low_dir
        or "borang_penyelidikan" in low_dir
    ):
        form_sub = "staff_forms"
    else:
        form_sub = "student_forms"

    return f"{college}/04_forms/{form_sub}/{school}/{target_fn}"


def build_plan():
    """Scan circular_forms/ and compute a deterministic, verified action plan."""
    artifacts = []
    # Check root circular_forms artifacts too (e.g., circular_Forms_tracker.xlsx:Zone.Identifier)
    for root, _, files in os.walk(CIRCULAR_FORMS_DIR):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            if is_temp_artifact(fn):
                artifacts.append(os.path.relpath(fp, BASE_DIR))

    notes = []
    doc_records = []
    for root, _, files in os.walk(COLLEGE_DIR):
        for fn in sorted(files):
            if is_temp_artifact(fn) or fn == NOTES_FILENAME:
                continue
            fp = os.path.join(root, fn)
            rel_cd = os.path.relpath(fp, COLLEGE_DIR).replace("\\", "/")
            if fn.lower() == "ps.txt":
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    notes.append((rel_cd, f.read().strip()))
                continue
            doc_records.append({
                "rel_cd": rel_cd,
                "abs_path": fp,
                "sha256": sha256_file(fp),
                "size": os.path.getsize(fp),
            })

    all_rel_set = {r["rel_cd"] for r in doc_records}

    # Group by SHA-256 to deduplicate byte-for-byte identical files safely
    by_hash = collections.defaultdict(list)
    for rec in doc_records:
        by_hash[rec["sha256"]].append(rec)

    moves = []
    duplicates = []
    dest_map = {}

    for h, group in sorted(by_hash.items(), key=lambda x: x[1][0]["rel_cd"]):
        ranked = sorted(group, key=lambda r: clean_canonical_rank(r["rel_cd"]))
        winner = ranked[0]
        target_rel = classify_document(winner["rel_cd"], all_rel_set)

        # Collision check: if two DIFFERENT SHA-256 files map to the exact same destination, disambiguate safely
        if target_rel in dest_map and dest_map[target_rel]["sha256"] != h:
            # Disambiguate using immediate parent folder tag rather than ever overwriting
            parent_tag = winner["rel_cd"].split("/")[-2]
            stem, ext = os.path.splitext(target_rel)
            alt_target = f"{stem}_{parent_tag}{ext}"
            if alt_target in dest_map and dest_map[alt_target]["sha256"] != h:
                raise RuntimeError(f"Unresolved path collision at {target_rel} from {winner['rel_cd']}")
            target_rel = alt_target

        dest_map[target_rel] = winner
        moves.append({
            "old_rel": winner["rel_cd"],
            "new_rel": target_rel,
            "sha256": h,
            "size": winner["size"],
            "action": "keep_in_place" if winner["rel_cd"] == target_rel else "move",
        })

        for extra in ranked[1:]:
            duplicates.append({
                "old_rel": extra["rel_cd"],
                "kept_rel": target_rel,
                "canonical_source": winner["rel_cd"],
                "sha256": h,
                "size": extra["size"],
                "action": "remove_exact_duplicate",
            })

    return {
        "artifacts": sorted(artifacts),
        "notes": sorted(notes, key=lambda x: x[0]),
        "moves": sorted(moves, key=lambda x: x["new_rel"]),
        "duplicates": sorted(duplicates, key=lambda x: x["old_rel"]),
        "unique_hashes": set(by_hash.keys()),
    }


def render_notes_markdown(notes):
    lines = [
        "# College Documents Collection Notes (`ps.txt` Archive)",
        "",
        "Consolidated notes recorded during document collection from UUM school portals.",
        "",
        "| Original Folder | Note |",
        "| :--- | :--- |",
    ]
    for rel_cd, text in notes:
        folder = os.path.dirname(rel_cd)
        clean_txt = " / ".join(l.strip() for l in text.splitlines() if l.strip()) or "*(empty note)*"
        clean_txt = clean_txt.replace("|", "\\|")
        lines.append(f"| `{folder}` | {clean_txt} |")
    lines.append("")
    return "\n".join(lines)


def execute_plan(plan):
    manifest_entries = []

    # 1. Write consolidated COLLECTION_NOTES.md & remove loose ps.txt files
    if plan["notes"]:
        notes_out = os.path.join(COLLEGE_DIR, NOTES_FILENAME)
        with open(notes_out, "w", encoding="utf-8") as f:
            f.write(render_notes_markdown(plan["notes"]))
        for rel_cd, text in plan["notes"]:
            src_ps = os.path.join(COLLEGE_DIR, rel_cd)
            if os.path.exists(src_ps):
                os.remove(src_ps)
            manifest_entries.append({
                "old_path": f"circular_forms/College_documents/{rel_cd}",
                "new_path": f"circular_forms/College_documents/{NOTES_FILENAME}",
                "sha256": None,
                "action": "consolidated_ps_note",
            })

    # 2. Remove temp/Zone.Identifier artifacts
    for rel_art in plan["artifacts"]:
        art_fp = os.path.join(BASE_DIR, rel_art)
        if os.path.exists(art_fp):
            os.remove(art_fp)
        manifest_entries.append({
            "old_path": rel_art,
            "new_path": None,
            "sha256": None,
            "action": "removed_temp_artifact",
        })

    # 3. Stage moves via temporary directory inside College_documents to avoid any self-move/case issues
    staging_dir = os.path.join(COLLEGE_DIR, ".reorg_staging_tmp")
    os.makedirs(staging_dir, exist_ok=True)

    staged = []
    for idx, mv in enumerate(plan["moves"]):
        src = os.path.join(COLLEGE_DIR, mv["old_rel"])
        dst = os.path.join(COLLEGE_DIR, mv["new_rel"])
        if mv["action"] == "keep_in_place":
            manifest_entries.append({
                "old_path": f"circular_forms/College_documents/{mv['old_rel']}",
                "new_path": f"circular_forms/College_documents/{mv['new_rel']}",
                "sha256": mv["sha256"],
                "action": "keep_in_place",
            })
            continue
        stage_fp = os.path.join(staging_dir, f"item_{idx:04d}")
        shutil.move(src, stage_fp)
        staged.append((stage_fp, dst, mv))

    # 4. Remove verified byte-identical SHA-256 duplicate files
    for dup in plan["duplicates"]:
        dup_fp = os.path.join(COLLEGE_DIR, dup["old_rel"])
        if os.path.exists(dup_fp):
            actual_hash = sha256_file(dup_fp)
            if actual_hash != dup["sha256"]:
                raise RuntimeError(f"Hash mismatch before removing duplicate: {dup_fp}")
            os.remove(dup_fp)
        manifest_entries.append({
            "old_path": f"circular_forms/College_documents/{dup['old_rel']}",
            "new_path": f"circular_forms/College_documents/{dup['kept_rel']}",
            "sha256": dup["sha256"],
            "action": "removed_exact_duplicate",
        })

    # 5. Move staged files into standardized final destinations
    for stage_fp, dst, mv in staged:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            raise RuntimeError(f"Refusing to overwrite existing destination file: {dst}")
        shutil.move(stage_fp, dst)
        manifest_entries.append({
            "old_path": f"circular_forms/College_documents/{mv['old_rel']}",
            "new_path": f"circular_forms/College_documents/{mv['new_rel']}",
            "sha256": mv["sha256"],
            "action": "moved",
        })

    if os.path.exists(staging_dir):
        os.rmdir(staging_dir)

    # 6. Prune all empty directories bottom-up inside College_documents
    pruned_dirs = 0
    for root, dirs, files in os.walk(COLLEGE_DIR, topdown=False):
        if root == COLLEGE_DIR:
            continue
        if not os.listdir(root):
            os.rmdir(root)
            pruned_dirs += 1

    # 7. Post-move integrity verification
    post_hashes = set()
    for root, _, files in os.walk(COLLEGE_DIR):
        for fn in files:
            if fn == NOTES_FILENAME:
                continue
            post_hashes.add(sha256_file(os.path.join(root, fn)))

    missing = plan["unique_hashes"] - post_hashes
    if missing:
        raise RuntimeError(f"CRITICAL: {len(missing)} unique hashes missing after reorganization!")

    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_entries, f, indent=2)

    return pruned_dirs


def main():
    parser = argparse.ArgumentParser(description="Standardize circular_forms/College_documents/")
    parser.add_argument("--dry-run", action="store_true", help="Preview standardization without modifying disk")
    args = parser.parse_args()

    plan = build_plan()

    folder_counts = collections.Counter()
    disambiguated = []
    for mv in plan["moves"]:
        top2 = "/".join(mv["new_rel"].split("/")[:2])
        folder_counts[top2] += 1
        if os.path.basename(mv["old_rel"]) != os.path.basename(mv["new_rel"]):
            disambiguated.append((mv["old_rel"], mv["new_rel"]))

    print("=" * 72)
    print(f"  UUM COLLEGE DOCUMENTS STANDARDIZER ({'DRY RUN' if args.dry_run else 'LIVE EXECUTION'})")
    print("=" * 72)
    print(f"  • Unique real documents mapped : {len(plan['moves'])}")
    print(f"  • Exact SHA-256 duplicates     : {len(plan['duplicates'])}")
    print(f"  • Collection notes (ps.txt)    : {len(plan['notes'])}")
    print(f"  • Temp / Zone.Identifier files : {len(plan['artifacts'])}")
    print("-" * 72)
    print("  Target Category Breakdown:")
    for cat, cnt in sorted(folder_counts.items()):
        print(f"    - {cat:<42} : {cnt:>3} files")

    if disambiguated:
        print("-" * 72)
        print(f"  Renamed / Disambiguated Files ({len(disambiguated)}):")
        for old_r, new_r in disambiguated:
            print(f"    * {old_r}\n      -> {new_r}")

    if args.dry_run:
        print("=" * 72)
        print("  [✓] Dry-run verification passed (100% hash coverage, 0 unresolved collisions).")
        return

    pruned = execute_plan(plan)
    print("-" * 72)
    print(f"  [✓] Consolidated notes written : circular_forms/College_documents/{NOTES_FILENAME}")
    print(f"  [✓] Audit manifest saved       : {os.path.relpath(MANIFEST_PATH, BASE_DIR)}")
    print(f"  [✓] Empty directories pruned   : {pruned}")
    print("  [✓] Post-move SHA-256 check    : PASSED (100% unique documents verified)")
    print("=" * 72)


if __name__ == "__main__":
    main()
