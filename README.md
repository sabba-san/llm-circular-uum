# UUM Circular & Project Document Intelligence System (LLM)

**Product Requirements & Implementation (Phase 1: Data Collection & Cataloging)**  
*Prepared by: Ahmad Abbas & Lia*  
*Universiti Utara Malaysia (UUM)*

---

## 📌 Project Overview
The **UUM Circular & Project Document Intelligence System** is an LLM-powered Retrieval-Augmented Generation (RAG) assistant designed to centralize and navigate administrative circulars (*Pekeliling*), SOPs, guidelines, and project forms across all Universiti Utara Malaysia (UUM) centers of authority (PTJs):
- **RMC** (Research Management Centre)
- **Jabatan Bendahari** (Bursar's Office)
- **ICC** (Innovation & Commercialization Center)
- **JUU** (Jabatan Undang-Undang / Legal Office)

Users can query the system in natural language (Bahasa Melayu & English) to generate comprehensive document checklists, required approval forms, and clause-level citations for university research grants, consultancy, commercialization, and financial claims.

---

## 📁 Repository Structure

```
llm_uum/
├── PRD_ UUM Circular & Project Document Intelligence System (LLM).docx  # Official System PRD
├── circular_Forms_tracker.xlsx                                         # Master Excel Tracker (circulars & forms)
├── sort_tracker.py                                                     # Automated extraction, OCR & sorting tool
├── .metadata_cache.json                                                # Pre-extracted metadata cache (<1s runs)
├── .gitignore                                                          # Git exclusion rules
├── README.md                                                           # Project documentation
│
└── circular_forms/                                                     # Collected Document Corpus (95 MB)
    ├── Bedahari/                                                       # Jabatan Bendahari Collection (Abbas)
    │   ├── 02_Circulars/                                               # 141 Circulars (2009 - 2026)
    │   └── 02_forms/                                                   # 38 Official Forms & Templates
    │
    ├── RMC/                                                            # Research Management Centre (Abbas)
    │   ├── 01_Circulars/                                               # 28 Circulars & Guidelines (Senat 326, etc.)
    │   └── 01_Forms/                                                   # 20 Forms (RMC 001 - RMC 023, RaIIS, etc.)
    │
    ├── ICC/                                                            # Innovation & Commercialization (Lia)
    │   ├── 03_Circulars/                                               # (Pending Phase 1 Collection)
    │   └── 03_forms/                                                   # (Pending Phase 1 Collection)
    │
    └── JUU/                                                            # Jabatan Undang-Undang / Legal (Lia)
        ├── 04_circulars/                                               # (Pending Phase 1 Collection)
        └── 04_forms/                                                   # (Pending Phase 1 Collection)
```

---

## 🚀 Automated Tracker & Sorter (`sort_tracker.py`)

A standalone CLI tool that processes all documents in `circular_forms/`, extracts layout text & performs OCR fallback on scanned documents, tags lifecycle status (**Active** vs **Superseded**), maps forms to their governing circulars, and updates [`circular_Forms_tracker.xlsx`](./circular_Forms_tracker.xlsx).

### Running the Tool:
```bash
python3 sort_tracker.py
```
*(Runs in under 1 second using cached metadata in `.metadata_cache.json`)*.

### CLI Options:
```bash
# Clean Windows artifact files (:Zone.Identifier / desktop.ini)
python3 sort_tracker.py --clean

# Export full metadata as JSON for Phase 2 database ingestion
python3 sort_tracker.py --export-json metadata.json

# Force a fresh re-extraction and OCR on all documents
python3 sort_tracker.py --force-ocr
```

---

## 📊 Master Tracker Overview (`circular_Forms_tracker.xlsx`)

- **Sheet 1 (`circulars`)**:
  - **168 unique circulars** cataloged across Jabatan Bendahari and RMC.
  - **120 Active** (`Berkuat Kuasa`) and **48 Superseded** (`Terbatal`) circulars.
  - Sorted by **Department**, **Status** (Active first), **Category**, and **Date (Descending)**.
- **Sheet 2 (`forms`)**:
  - **58 official forms and templates** mapped to project activity types (e.g., `KEW.PA` series, `RMC 001–023`, `BEN-PO-01`, `BEN-TRV-01`).
  - Cross-referenced with governing circular references.

---

## 🗺️ Roadmap & Phase Distribution

| Phase | Timeline | Focus | Responsible |
| :--- | :--- | :--- | :--- |
| **Phase 1** | Weeks 1–2 | Data Collection & Cataloging (RMC, Bendahari, ICC, JUU) | **Abbas** (RMC, Bendahari) & **Lia** (ICC, JUU) |
| **Phase 2** | Weeks 3–4 | Data Cleaning, Parsing, Chunking & PostgreSQL/Vector DB Setup | Abbas & Lia |
| **Phase 3** | Weeks 5–6 | Hybrid RAG Pipeline, System Prompts & Web UI | Abbas & Lia |
| **Phase 4** | Week 7 | Scenario Evaluation & Final Presentation with Supervisor | Abbas & Lia |
