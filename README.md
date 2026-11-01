# UUM Circular & Project Document Intelligence System (LLM)

**A retrieval-augmented intelligence assistant for Universiti Utara Malaysia (UUM) circulars, guidelines, and project forms.**  
*Prepared by: Ahmad Abbas & Lia*  
*Universiti Utara Malaysia (UUM)*

---

## 📌 Project Overview
The **UUM Circular & Project Document Intelligence System** is an LLM-powered Retrieval-Augmented Generation (RAG) assistant designed to centralize and navigate administrative circulars (*Pekeliling*), SOPs, guidelines, and project forms across all Universiti Utara Malaysia (UUM) centers of authority (PTJs):
- **RMC** (Research Management Centre)
- **Jabatan Bendahari** (Bursar's Office)
- **ICC** (Innovation & Commercialization Center)
- **JUU** (Jabatan Undang-Undang / Legal Office)

Users can query the system in natural language (Bahasa Melayu & English) to retrieve exact clause-level citations, applicable circular reference numbers, effective dates, and mandatory forms/checklists for university research grants, consultancy, commercialization, and financial claims.

---

## 📁 Repository Structure

```
llm_uum/
├── ask.py                         # 🔍 Ask Assistant CLI (One-shot & Interactive Mode)
├── ingest.py                      # ⚡ Chunking & Database Ingestion CLI
├── sort.py                        # 📊 Circular & Form Auto-Sorter & OCR CLI
├── circular_Forms_tracker.xlsx    # Master Excel Tracker (circulars & forms catalog)
├── .env.example                   # Environment configuration template
├── requirements.txt               # Lightweight Python dependencies
├── README.md                      # Project documentation & usage guide
│
├── src/                           # 🧠 Modular Core System Package
│   ├── __init__.py                # Package initializer
│   ├── ai_provider.py             # Multi-API LLM Client (Gemini, Groq, OpenRouter)
│   ├── db.py                      # Dual-mode Database Setup (PostgreSQL + pgvector / SQLite)
│   ├── ingestion.py               # Document Chunking, Semantic Embedding & Ingestion
│   ├── search.py                  # Hybrid Search (BM25 + Semantic Vector Retrieval)
│   └── tracker_sorter.py          # Auto-Sorter, OCR fallback, & Tracker Generator
│
├── docs/                          # 📄 System Documentation
│   └── PRD_... (LLM).docx         # Official System PRD & Specification
│
├── data/                          # 💾 Local Knowledge Base & Databases
│   └── uum_knowledge.db           # SQLite FTS5 Full-Text & Vector Database (git-ignored)
│
├── circular_forms/                # 📂 Collected Document Corpus (95 MB)
│   ├── Bedahari/                  # Jabatan Bendahari Collection (Abbas)
│   │   ├── 02_Circulars/          # 141 Circulars (2009 - 2026)
│   │   └── 02_forms/              # 38 Official Forms & Templates
│   ├── RMC/                       # Research Management Centre (Abbas)
│   │   ├── 01_Circulars/          # 28 Circulars & Guidelines (Senat 326, etc.)
│   │   └── 01_Forms/              # 20 Forms (RMC 001 - RMC 023, RaIIS, etc.)
│   ├── ICC/                       # Innovation & Commercialization (Lia)
│   │   ├── 03_Circulars/          # (Phase 1 Collection)
│   │   └── 03_forms/              # (Phase 1 Collection)
│   └── JUU/                       # Jabatan Undang-Undang / Legal (Lia)
│       ├── 04_circulars/          # (Phase 1 Collection)
│       └── 04_forms/              # (Phase 1 Collection)
│
└── [Legacy Compatibility Wrappers]
    ├── sort_tracker.py            # -> calls src/tracker_sorter.py
    ├── ask_uum.py                 # -> calls ask.py
    ├── ingest_to_postgres.py      # -> calls src/ingestion.py
    └── db_setup.py                # -> calls src/db.py
```

---

## ⚡ Quick Start

### 1. Installation
Clone the repository and set up a virtual environment:
```bash
git clone https://github.com/sabba-san/llm-circular-uum.git
cd llm-circular-uum

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Copy the example template:
```bash
cp .env.example .env
```
Edit `.env` to configure your keys:
- **`DATABASE_URL`**: Leave blank to use the built-in local SQLite database (`data/uum_knowledge.db`), or provide a PostgreSQL connection URL (e.g. from Neon / Supabase).
- **`GEMINI_API_KEY`**: (Free tier) Get your free key at [Google AI Studio](https://aistudio.google.com/app/apikey).
- **`GROQ_API_KEY`**: (Optional high-speed fallback) Get your free key at [Groq Console](https://console.groq.com/keys).
- **`OPENROUTER_API_KEY`**: (Optional fallback) Get your key at [OpenRouter](https://openrouter.ai).

> **Note**: Even **without any API keys configured**, the system works out-of-the-box in **Offline Extractive Mode**, returning exact clause citations and mandatory forms from the local index!

---

## 🚀 CLI Commands

### 1. Ask Assistant (`ask.py`)
Run a one-shot query:
```bash
python3 ask.py "Berapakah kadar bayaran penceramah luar untuk kakitangan swasta?"
```

Or launch interactive chat mode:
```bash
python3 ask.py -i
# or
python3 ask.py --interactive
```

Example query topics:
- *"Apakah syarat lantikan GRA di bawah geran penyelidikan?"*
- *"Bagaimana proses permohonan pendahuluan diri untuk perjalanan rasmi?"*
- *"Apakah borang yang perlu diisi bagi pelupusan aset universiti?"*

---

### 2. Ingest & Chunk Documents (`ingest.py`)
Parses all circulars & forms from `circular_Forms_tracker.xlsx`, splits text into clause-level chunks, computes vector embeddings, and builds the search index:
```bash
python3 ingest.py
```
- Builds **3,500+ indexed chunks** across all departments.
- Supports dual storage: automatically writes to PostgreSQL + `pgvector` when `DATABASE_URL` is set, or SQLite FTS5 when running locally.

---

### 3. Auto-Sort Documents & Update Tracker (`sort.py`)
Scans `circular_forms/`, extracts metadata via layout text and OCR, links forms to governing circulars, and updates [`circular_Forms_tracker.xlsx`](./circular_Forms_tracker.xlsx):
```bash
python3 sort.py
```

Options:
```bash
# Clean Windows artifact files (:Zone.Identifier / desktop.ini)
python3 sort.py --clean

# Export extracted metadata to JSON
python3 sort.py --export-json metadata.json

# Force full re-extraction & OCR ignoring cache
python3 sort.py --force-ocr
```

---

## 🛡️ Multi-Provider AI Architecture

The system implements a resilient multi-tier fallback architecture in `src/ai_provider.py`:

```
User Query
    │
    ▼
[Hybrid Search Engine] (BM25 Keyword + Cosine Vector Retrieval)
    │
    ▼
Top Retrieved Context Chunks (Clause, Page, Ref No, Forms)
    │
    ├── Tier 1: Google Gemini 1.5 Flash (Primary)
    │       └── Failed / Rate-limited? ──► Tier 2: Groq Llama 3.3 70B (High-speed)
    │                                              └── Failed? ──► Tier 3: OpenRouter
    │                                                                   └── No Keys? ──► Tier 4: Offline Extractive Engine
    ▼
Synthesized Answer with Exact Citations & Mandatory Forms Checklist
```

---

## 📊 Document Corpus Statistics
- **Total Cataloged Circulars**: 175 (Jabatan Bendahari: 141, RMC: 28, ICC & JUU: Active Collection)
- **Total Cataloged Forms**: 74 (KEW.PA series, RMC 001–023, BEN series, etc.)
- **Semantic Text Chunks**: 3,527 chunks indexed with section headings and page citations.
- **Corpus Footprint**: 95 MB (227 PDF and document files).

---

## 🗺️ Roadmap & Phase Distribution

| Phase | Focus | Status |
| :--- | :--- | :--- |
| **Phase 1** | Data Collection & Cataloging (RMC, Bendahari, ICC, JUU) | ✅ Completed |
| **Phase 2** | Cleaning, Parsing, Chunking & Dual Database Setup (PostgreSQL + SQLite) | ✅ Completed |
| **Phase 3** | Hybrid RAG Pipeline, Multi-API Fallback & CLI Assistant | ✅ Completed |
| **Phase 4** | Web UI (Streamlit / FastHTML) & Final Presentation | 🔄 Next Step |
