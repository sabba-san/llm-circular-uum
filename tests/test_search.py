"""Baseline tests for hybrid search, metadata filtering, and offline extractive mode."""

from src.search import UUMAssistant


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
