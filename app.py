#!/usr/bin/env python3
"""
UUM Circular & Project Document Intelligence System (Phase 4)
Interactive Web Application & Evaluation Dashboard

Authors: Ahmad Abbas & Lia
Universiti Utara Malaysia (UUM)
"""

import os
import sys
import sqlite3
import pandas as pd
import streamlit as st

from src.ai_provider import AIProvider, load_env, find_root_dir, is_english_query
from src.search import UUMAssistant
from src.tracker_sorter import main as run_sorter
from src.ingestion import run_ingestion

load_env()
ROOT_DIR = find_root_dir()
SQLITE_DB = os.path.join(ROOT_DIR, "data", "uum_knowledge.db")
EXCEL_TRACKER = os.path.join(ROOT_DIR, "circular_Forms_tracker.xlsx")

# -----------------------------------------------------------------------------
# Page Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="UUM Circular & Document Intelligence",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (UUM Blue & Crimson Palette)
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #0d233a;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4f5d75;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 12px;
        border-left: 4px solid #1e3d59;
        margin-bottom: 10px;
    }
    .badge-active {
        background-color: #d4edda;
        color: #155724;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .badge-form {
        background-color: #e2e3e5;
        color: #383d41;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.85em;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Database Helper Functions
# -----------------------------------------------------------------------------
@st.cache_data(ttl=60)
def load_catalog_data():
    """Load circulars and forms tables from SQLite."""
    if not os.path.exists(SQLITE_DB):
        return pd.DataFrame(), pd.DataFrame(), {}
    
    con = sqlite3.connect(SQLITE_DB)
    try:
        df_circ = pd.read_sql_query("SELECT * FROM circulars ORDER BY department, status, year DESC;", con)
        df_forms = pd.read_sql_query("SELECT * FROM required_documents_forms ORDER BY department, form_code;", con)
        cur = con.cursor()
        cur.execute("SELECT count(*) FROM document_chunks;")
        total_chunks = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM circulars WHERE status = 'Active';")
        active_circ = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM circulars WHERE status = 'Superseded';")
        superseded_circ = cur.fetchone()[0]
        
        stats = {
            "total_circulars": len(df_circ),
            "active_circulars": active_circ,
            "superseded_circulars": superseded_circ,
            "total_forms": len(df_forms),
            "total_chunks": total_chunks
        }
        return df_circ, df_forms, stats
    finally:
        con.close()

# -----------------------------------------------------------------------------
# Sidebar: System Health, Metrics & Supervisor Demo Benchmarks
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/Universiti_Utara_Malaysia_Logo.svg/1200px-Universiti_Utara_Malaysia_Logo.svg.png", width=140)
    st.markdown("### 🏛️ UUM Intelligence System")
    st.markdown("**PTJ Coverage:**\n* RMC • Bendahari • ICC • JUU")
    
    df_circ, df_forms, stats = load_catalog_data()
    
    st.markdown("---")
    st.markdown("#### 📊 Knowledge Base Stats")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Circulars", stats.get("total_circulars", 0), f"{stats.get('active_circulars', 0)} Active")
    with col2:
        st.metric("Forms", stats.get("total_forms", 0))
    st.metric("Indexed Chunks", f"{stats.get('total_chunks', 0):,}", "768-d Vectors")
    
    ai_status = "Google Gemini Flash" if os.environ.get("GEMINI_API_KEY") else "Offline Extractive Engine"
    st.caption(f"🧠 **AI Engine:** `{ai_status}`")
    st.caption(f"💾 **Vector Store:** `SQLite FTS5 + pgvector`")

    st.markdown("---")
    st.markdown("#### 🎓 Supervisor Demo Benchmarks")
    st.caption("Click any scenario to run an instant test query:")

    benchmark_queries = {
        "🎓 GRA Appointment (English)": "What are the requirements and allowance ceilings to appoint a Graduate Research Assistant (GRA)?",
        "🎤 Speaker Honorarium (BM)": "Apakah kadar bayaran penceramah luar bagi sektor swasta?",
        "✈️ Travel Advance (BM)": "Bagaimanakah prosedur permohonan pendahuluan diri untuk perjalanan rasmi?",
        "📦 Asset Disposal & KEW.PA (BM)": "Apakah proses dan borang yang diperlukan untuk pelupusan aset universiti?",
        "💼 Consultancy via RaIIS (English)": "What is the procedure for UUM staff consultancy projects funded by spin-off companies?",
    }

    for label, query_text in benchmark_queries.items():
        if st.button(label, use_container_width=True):
            st.session_state["pending_query"] = query_text

    st.markdown("---")
    st.markdown("#### ⚡ Pipeline Management")
    if st.button("🔄 Sync Pipeline (sort + ingest)", use_container_width=True):
        with st.spinner("Running full automation pipeline..."):
            run_sorter()
            run_ingestion()
            st.cache_data.clear()
            st.success("Pipeline successfully synced!")
            st.rerun()

    if st.button("🧹 Clear Chat History", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()

# -----------------------------------------------------------------------------
# Main Application Tabs
# -----------------------------------------------------------------------------
st.markdown('<div class="main-header">UUM Circular & Project Document Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Retrieval-Augmented Generation (RAG) Assistant for Universiti Utara Malaysia administrative, financial, and research regulations.</div>', unsafe_allow_html=True)

tab_chat, tab_catalog, tab_arch = st.tabs(["💬 AI Assistant (RAG Chat)", "📋 Master Document Catalog", "ℹ️ System Architecture & PRD"])

# Initialize Chat Memory
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": "Selamat datang! Saya ialah **Pembantu Pintar Pekeliling UUM**. Anda boleh bertanya sebarang soalan mengenai pekeliling pentadbiran, kewangan, penyelidikan (RMC), dan perundangan dalam **Bahasa Melayu** atau **English**.",
            "sources": []
        }
    ]

# -----------------------------------------------------------------------------
# TAB 1: AI Chat Assistant (RAG)
# -----------------------------------------------------------------------------
with tab_chat:
    # Display message history
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander(f"📚 View Official Citations ({len(msg['sources'])} Sources Checked)", expanded=False):
                    for idx, s in enumerate(msg["sources"], 1):
                        forms_str = f" • **Required Forms:** `{s['required_forms']}`" if s.get("required_forms") and s['required_forms'] != "-" else ""
                        st.markdown(
                            f"**[{idx}] {s['circular_ref_no']} ({s['department']})** — *Page {s['page_number']}*\n"
                            f"> **Section:** {s['section_heading']}{forms_str}\n"
                            f"> *\"{s['chunk_text'][:200]}...\"*"
                        )

    # Check for pending query from benchmark buttons
    query_to_process = None
    if "pending_query" in st.session_state and st.session_state["pending_query"]:
        query_to_process = st.session_state["pending_query"]
        del st.session_state["pending_query"]

    # Chat Input Box
    user_input = st.chat_input("Tanya sebarang soalan pekeliling / Ask any circular or guideline question...")
    if user_input:
        query_to_process = user_input

    if query_to_process:
        # Display user question
        st.session_state["messages"].append({"role": "user", "content": query_to_process, "sources": []})
        with st.chat_message("user"):
            st.markdown(query_to_process)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Searching UUM knowledge base and synthesizing clause citations..."):
                assistant = UUMAssistant()
                res = assistant.ask(query_to_process)
                answer = res["answer"]
                sources = res["sources"]
                provider = res["provider"]

                st.markdown(answer)
                if sources:
                    with st.expander(f"📚 View Official Citations ({len(sources)} Sources Checked)", expanded=True):
                        for idx, s in enumerate(sources, 1):
                            forms_str = f" • **Borang/Forms:** `{s['required_forms']}`" if s.get("required_forms") and s['required_forms'] != "-" else ""
                            st.markdown(
                                f"**[{idx}] {s['circular_ref_no']} ({s['department']})** — *Page {s['page_number']}*\n"
                                f"> **Clause/Section:** {s['section_heading']}{forms_str}\n"
                                f"> *\"{s['chunk_text'][:220]}...\"*"
                            )
                st.caption(f"Generated via `{provider}` • Dual Retrieval (BM25 + Dense Vector)")

        st.session_state["messages"].append({
            "role": "assistant",
            "content": answer,
            "sources": sources
        })

# -----------------------------------------------------------------------------
# TAB 2: Master Document Catalog Explorer
# -----------------------------------------------------------------------------
with tab_catalog:
    st.markdown("### 📋 Master Document & Form Catalog Explorer")
    st.caption("Interactive browser for all cataloged administrative circulars and project forms across UUM PTJs.")

    col_view, col_dl = st.columns([3, 1])
    with col_view:
        view_mode = st.radio("Select View:", ["📜 Pekeliling & Guidelines (Circulars)", "📑 Borang & Checklists (Forms)"], horizontal=True)
    with col_dl:
        if os.path.exists(EXCEL_TRACKER):
            with open(EXCEL_TRACKER, "rb") as f:
                st.download_button(
                    label="📥 Download Master Excel",
                    data=f.read(),
                    file_name="circular_Forms_tracker.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

    if view_mode.startswith("📜"):
        # Filters for circulars
        fcol1, fcol2, fcol3 = st.columns(3)
        with fcol1:
            depts = ["All"] + sorted(list(df_circ["department"].dropna().unique()))
            sel_dept = st.selectbox("Filter by Department (PTJ):", depts)
        with fcol2:
            statuses = ["All"] + sorted(list(df_circ["status"].dropna().unique()))
            sel_status = st.selectbox("Filter by Status:", statuses)
        with fcol3:
            search_kw = st.text_input("Search Keyword / Ref No:", placeholder="e.g. Geran, Bil. 8, FRGS")

        filtered_df = df_circ.copy()
        if sel_dept != "All":
            filtered_df = filtered_df[filtered_df["department"] == sel_dept]
        if sel_status != "All":
            filtered_df = filtered_df[filtered_df["status"] == sel_status]
        if search_kw:
            kw = search_kw.lower()
            filtered_df = filtered_df[
                filtered_df["title"].str.lower().str.contains(kw, na=False) |
                filtered_df["ref_no"].str.lower().str.contains(kw, na=False) |
                filtered_df["category"].str.lower().str.contains(kw, na=False)
            ]

        st.markdown(f"**Showing {len(filtered_df)} of {len(df_circ)} circulars**")
        st.dataframe(
            filtered_df[["ref_no", "title", "department", "category", "effective_date", "status", "required_forms"]],
            use_container_width=True,
            hide_index=True
        )

    else:
        # Filters for forms
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            depts = ["All"] + sorted(list(df_forms["department"].dropna().unique()))
            sel_dept = st.selectbox("Filter by Department (PTJ):", depts, key="forms_dept")
        with fcol2:
            search_form = st.text_input("Search Form Code / Title:", placeholder="e.g. RMC 008, KEW.PA, RaIIS", key="forms_search")

        filtered_forms = df_forms.copy()
        if sel_dept != "All":
            filtered_forms = filtered_forms[filtered_forms["department"] == sel_dept]
        if search_form:
            kw = search_form.lower()
            filtered_forms = filtered_forms[
                filtered_forms["form_code"].str.lower().str.contains(kw, na=False) |
                filtered_forms["form_title"].str.lower().str.contains(kw, na=False) |
                filtered_forms["related_circular"].str.lower().str.contains(kw, na=False)
            ]

        st.markdown(f"**Showing {len(filtered_forms)} of {len(df_forms)} official forms**")
        st.dataframe(
            filtered_forms[["form_code", "form_title", "department", "related_circular", "project_activity_type", "is_mandatory"]],
            use_container_width=True,
            hide_index=True
        )

# -----------------------------------------------------------------------------
# TAB 3: System Architecture & PRD Roadmap
# -----------------------------------------------------------------------------
with tab_arch:
    st.markdown("### 🏛️ System Architecture & PRD Alignment")
    
    st.markdown("""
    #### 1. Hybrid Retrieval Pipeline (BM25 + Semantic Vector Fusion)
    The system blends keyword frequency matching with high-dimensional cross-lingual embeddings to overcome terminology mismatches:
    """)
    st.code("""
User Query (English / BM)
    │
    ├──► Cross-Lingual Term Expansion (English -> Malay administrative keywords)
    │
    ├──► BM25 Keyword Search (SQLite FTS5 / PostgreSQL tsvector) [Weight: 40%]
    │        - Matches exact circular numbers: Bil. 8/2025, Senat 326, PK 7.1
    │        - Matches exact form codes: RMC 008, KEW.PA-1, RaIIS
    │
    ├──► Dense Semantic Vector Search (Gemini gemini-embedding-001 at 768-d) [Weight: 60%]
    │        - Computes Cosine Similarity against 3,527 clause-level chunks
    │        - Matches conceptual intent across English & Bahasa Melayu
    │
    ▼
Hybrid Rank Fusion (Score = 0.6 * Vec + 0.4 * BM25)
    │
    ▼
Active Lifecycle Filter (Automatically excludes Superseded circulars)
    │
    ▼
Top 4 Verified Context Chunks injected into LLM Prompt
    │
    ▼
Google Gemini Flash Synthesis (100% Language Mirroring + Citations)
    """, language="text")

    st.markdown("---")
    st.markdown("#### 2. PRD Phase Roadmap & Delivery Status")
    st.markdown("""
    | Phase | Focus | Status |
    | :--- | :--- | :---: |
    | **Phase 1** | Data Collection & Master Cataloging (RMC, Bendahari, ICC, JUU) | ✅ **Completed** (175 circulars, 74 forms) |
    | **Phase 2** | Layout-Aware Parsing, Semantic Chunking & Vector DB Setup | ✅ **Completed** (3,527 chunks indexed) |
    | **Phase 3** | Multi-Provider Failover, Bilingual Mirroring & CLI Assistant | ✅ **Completed** (ask.py with exact citations) |
    | **Phase 4** | Interactive Web Dashboard, Evaluation & Supervisor Presentation | 🚀 **Active & Deployed** (Streamlit Web UI) |
    """)

st.caption("UUM Circular & Project Document Intelligence System • Prepared for Ahmad Abbas & Lia • Universiti Utara Malaysia")
