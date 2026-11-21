"""Baseline tests for hybrid search, metadata filtering, and offline extractive mode."""

from concurrent.futures import ThreadPoolExecutor
from src.search import UUMAssistant, _is_junk_chunk


def _make_offline_assistant(monkeypatch):
    """Create a UUMAssistant instance with all external LLM API keys disabled."""
    for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assistant = UUMAssistant()
    assistant.ai.gemini_key = ""
    assistant.ai.groq_key = ""
    assistant.ai.openrouter_key = ""
    return assistant


def test_rmc_008_hybrid_ranking(monkeypatch):
    """60/40 rank fusion surfaces RMC 008 chunks and computes combined_score."""
    assistant = _make_offline_assistant(monkeypatch)
    results = assistant.hybrid_search("RMC 008", top_k=6, filter_active=True, scope="All")

    assert len(results) > 0
    scores = [r["combined_score"] for r in results]
    assert scores == sorted(scores, reverse=True)

    for r in results:
        assert "vec_score" in r and "bm25_score" in r and "combined_score" in r
        assert 0.0 <= r["combined_score"] <= 1.0

    assert any(
        "RMC 008" in (r.get("chunk_text", "") + " " + r.get("circular_ref_no", ""))
        or "RMC" in r.get("department", "")
        for r in results
    )


def test_filter_active_excludes_superseded_and_respects_scope(monkeypatch):
    """filter_active=True excludes Superseded circulars and scope='RMC' narrows results."""
    assistant = _make_offline_assistant(monkeypatch)

    active_results = assistant.hybrid_search("pekeliling penyelidikan", top_k=10, filter_active=True, scope="All")
    assert all(r.get("status") != "Superseded" for r in active_results)

    rmc_results = assistant.hybrid_search("geran penyelidikan", top_k=6, filter_active=True, scope="RMC")
    assert len(rmc_results) > 0
    assert all(
        "rmc" in (r.get("department") or "").lower()
        or "research management" in (r.get("department") or "").lower()
        for r in rmc_results
    )


def test_tier4_offline_extractive_mode(monkeypatch):
    """With zero API keys, ask() falls back to Offline Extractive Engine and returns snippets."""
    assistant = _make_offline_assistant(monkeypatch)
    res = assistant.ask("Apakah syarat lantikan GRA?", filter_active=True, scope="All", top_k=5)

    assert res["provider"] == "Offline Extractive Engine"
    assert len(res["sources"]) > 0
    assert "Extractive Index Mode" in res["answer"]
    assert res["query"] == "Apakah syarat lantikan GRA?"
    assert 1 <= len(res["follow_up_questions"]) <= 3
    assert all(isinstance(q, str) and len(q) > 10 for q in res["follow_up_questions"])


def test_juu_scope_and_followup_previous_query(monkeypatch):
    """JUU legal statutes are searchable under scope='JUU' and previous_query disambiguates short follow-ups."""
    assistant = _make_offline_assistant(monkeypatch)
    juu_results = assistant.hybrid_search("Statut Senat", top_k=5, filter_active=True, scope="JUU")
    assert len(juu_results) > 0
    assert all("juu" in (r.get("department") or "").lower() or "undang" in (r.get("department") or "").lower() for r in juu_results)

    res = assistant.ask("What are the deadlines for this?", filter_active=True, scope="Bendahari", previous_query="Bursar Circular 15/2015 Visiting Scholars")
    assert len(res["sources"]) > 0


def test_out_of_scope_query_returns_no_sources(monkeypatch):
    """Off-topic queries like 'what is 2+2' must not match stopword chunks or hallucinate answers."""
    assistant = _make_offline_assistant(monkeypatch)
    res = assistant.ask("what is 2+2", filter_active=True, scope="RMC", top_k=6)
    assert res["sources"] == []
    assert res["provider"] == "None"
    assert res["follow_up_questions"] == []
    assert res["language"] == "en"


def test_junk_chunk_filter_preserves_valid_headers():
    """Junk-stub detector filters form punctuation noise while keeping valid short circular refs."""
    assert _is_junk_chunk(":") is True
    assert _is_junk_chunk("e.g/cth :") is True
    assert _is_junk_chunk("1 0 2 0 1 0 4") is True
    assert _is_junk_chunk("Pekeliling Bil. 5/2026") is False
    assert _is_junk_chunk("Borang RMC 008") is False


def test_grant_query_returns_diverse_docs_and_respects_cap(monkeypatch):
    """'how to get a grant' must return diverse documents (max 2 chunks/doc), not 6 chunks of 1 form."""
    assistant = _make_offline_assistant(monkeypatch)
    results = assistant.hybrid_search("how to get a grant", top_k=6, filter_active=True, scope="All")
    assert len(results) >= 4
    unique_docs = {r["doc_id"] for r in results}
    assert len(unique_docs) >= 2
    for doc_id in unique_docs:
        count = sum(1 for r in results if r["doc_id"] == doc_id)
        assert count <= 2
    assert all(not _is_junk_chunk(r.get("chunk_text", "")) for r in results)


def test_thread_safe_concurrent_search(monkeypatch):
    """Concurrent searches across worker threads must succeed safely via thread-local SQLite."""
    assistant = _make_offline_assistant(monkeypatch)
    queries = ["RMC 008", "how to get a grant", "pelupusan aset", "minor course registration"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda q: assistant.hybrid_search(q, top_k=4), queries))
    assert all(len(r) > 0 for r in results)


def test_soc_query_prioritizes_soc_and_handles_multi_school_set(monkeypatch):
    """Queries naming SOC prioritize SOC handbooks over SLCP/SAPSP/SMMTC, and multi-school queries aren't penalized."""
    from src.search import _extract_school_targets

    assert _extract_school_targets("Bachelor of Science in IT at SOC") == {"soc"}
    assert _extract_school_targets("Compare SOC and SMMTC industrial training") == {"soc", "smmtc"}

    assistant = _make_offline_assistant(monkeypatch)
    q = "What are the core course and credit requirements for Bachelor of Science in Information Technology with Honours at SOC?"
    results = assistant.hybrid_search(q, top_k=6, filter_active=True, scope="CAS")
    assert len(results) > 0
    titles = [r.get("title", "") for r in results]
    assert "1.Ucapan Aluan Naib Canselor" not in titles
    assert "5.Yuran Pengajian" not in titles
    assert "SLCP" not in titles
    assert "SAPSP 26 27" not in titles
    assert any("soc" in (r.get("school", "") + " " + r.get("title", "")).lower() for r in results[:3])
