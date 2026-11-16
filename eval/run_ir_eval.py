#!/usr/bin/env python3
"""
IR Evaluation Benchmark for UUM Document Intelligence System (Proposal Phase 5).
Computes Precision@K, Recall@K, MRR@K, and nDCG@K (K=3, K=5) across EN, BM, and Cross-Lingual
queries, plus a semantic/BM25 weight ablation sweep.
"""

import json
import math
import os
import sqlite3
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.search import UUMAssistant

EVAL_SET_PATH = os.path.join(ROOT_DIR, "eval", "bilingual_eval_set.json")
RESULTS_PATH = os.path.join(ROOT_DIR, "eval", "baseline_results.json")
SQLITE_DB = os.path.join(ROOT_DIR, "data", "uum_knowledge.db")


def validate_ground_truth(eval_cases):
    """Verify every relevant doc_id exists and is Active in data/uum_knowledge.db."""
    con = sqlite3.connect(SQLITE_DB)
    try:
        active_ids = set()
        for tbl in ("circulars", "college_documents"):
            for (doc_id,) in con.execute(f"SELECT id FROM {tbl} WHERE status = 'Active'"):
                active_ids.add(doc_id)
        for tbl in ("required_documents_forms", "college_forms"):
            for (doc_id,) in con.execute(f"SELECT id FROM {tbl}"):
                active_ids.add(doc_id)

        missing = []
        for case in eval_cases:
            for doc_id in case["relevant_docs"]:
                if doc_id not in active_ids:
                    missing.append((case["id"], doc_id))
        if missing:
            raise ValueError(f"Ground-truth doc_ids missing or inactive in DB: {missing}")
    finally:
        con.close()


def deduplicate_doc_ids(results):
    """Deduplicate retrieved chunks by doc_id while preserving rank order."""
    seen = set()
    ordered = []
    for r in results:
        did = r.get("doc_id") or r.get("circular_id")
        if did and did not in seen:
            seen.add(did)
            ordered.append(did)
    return ordered


def compute_metrics_at_k(ranked_doc_ids, relevant_docs, k):
    """Compute Precision@K, Recall@K, MRR@K, and graded nDCG@K."""
    top_k = ranked_doc_ids[:k]
    rel_set = set(relevant_docs.keys())

    hits = sum(1 for d in top_k if d in rel_set)
    precision = hits / k
    recall = hits / len(rel_set) if rel_set else 0.0

    mrr = 0.0
    for idx, d in enumerate(top_k, start=1):
        if d in rel_set:
            mrr = 1.0 / idx
            break

    dcg = sum(((2 ** relevant_docs[d]) - 1) / math.log2(idx + 1) for idx, d in enumerate(top_k, start=1) if d in rel_set)
    ideal_rels = sorted(relevant_docs.values(), reverse=True)[:k]
    idcg = sum(((2 ** rel) - 1) / math.log2(idx + 1) for idx, rel in enumerate(ideal_rels, start=1))
    ndcg = (dcg / idcg) if idcg > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "mrr": mrr,
        "ndcg": ndcg,
    }


def aggregate_metrics(per_query_rows):
    """Average P@3, R@3, MRR@3, nDCG@3, P@5, R@5, MRR@5, nDCG@5 over a subset."""
    n = len(per_query_rows)
    if n == 0:
        return {}
    keys = ["p3", "r3", "mrr3", "ndcg3", "p5", "r5", "mrr5", "ndcg5"]
    return {k: round(sum(row["metrics"][k] for row in per_query_rows) / n, 4) for k in keys}


def evaluate_weights(assistant, eval_cases, semantic_weight, keyword_weight):
    """Run all queries for a given (semantic_weight, keyword_weight) pair."""
    per_query = []
    for case in eval_cases:
        raw_results = assistant.hybrid_search(
            case["query"],
            top_k=30,
            filter_active=case.get("filter_active", True),
            scope=case.get("scope", "All"),
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
        )
        ranked_docs = deduplicate_doc_ids(raw_results)
        m3 = compute_metrics_at_k(ranked_docs, case["relevant_docs"], 3)
        m5 = compute_metrics_at_k(ranked_docs, case["relevant_docs"], 5)
        per_query.append({
            "id": case["id"],
            "direction": case["direction"],
            "scope": case.get("scope", "All"),
            "query": case["query"],
            "relevant_docs": case["relevant_docs"],
            "retrieved_top5": ranked_docs[:5],
            "metrics": {
                "p3": round(m3["precision"], 4),
                "r3": round(m3["recall"], 4),
                "mrr3": round(m3["mrr"], 4),
                "ndcg3": round(m3["ndcg"], 4),
                "p5": round(m5["precision"], 4),
                "r5": round(m5["recall"], 4),
                "mrr5": round(m5["mrr"], 4),
                "ndcg5": round(m5["ndcg"], 4),
            },
        })

    directions = ["en", "bm", "cross_en_to_bm", "cross_bm_to_en"]
    summary = {"ALL": {"count": len(per_query), **aggregate_metrics(per_query)}}
    for d in directions:
        sub = [row for row in per_query if row["direction"] == d]
        summary[d] = {"count": len(sub), **aggregate_metrics(sub)}

    return per_query, summary


def print_table(title, rows, label_col):
    print(f"\n=== {title} ===")
    header = f"{label_col:<18} | {'N':>3} | {'P@3':>6} | {'R@3':>6} | {'MRR@3':>6} | {'nDCG@3':>6} | {'P@5':>6} | {'R@5':>6} | {'MRR@5':>6} | {'nDCG@5':>6}"
    print(header)
    print("-" * len(header))
    for label, s in rows:
        print(
            f"{label:<18} | {s['count']:>3} | "
            f"{s['p3']:>6.4f} | {s['r3']:>6.4f} | {s['mrr3']:>6.4f} | {s['ndcg3']:>6.4f} | "
            f"{s['p5']:>6.4f} | {s['r5']:>6.4f} | {s['mrr5']:>6.4f} | {s['ndcg5']:>6.4f}"
        )


def main():
    with open(EVAL_SET_PATH, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    validate_ground_truth(eval_cases)
    print(f"Validated {len(eval_cases)} ground-truth queries against {SQLITE_DB}.")

    assistant = UUMAssistant()
    # Probe whether live Gemini embeddings are reachable in the current environment
    probe_vec = assistant.ai.get_embedding("test")
    fallback_vec = assistant.ai._generate_fallback_vector("test", dim=768)
    using_live_gemini_embeddings = probe_vec != fallback_vec
    print(f"Embedding mode: {'Live Gemini (gemini-embedding-001)' if using_live_gemini_embeddings else 'Offline Hash Fallback Vectors'}")

    baseline_per_query, baseline_summary = evaluate_weights(assistant, eval_cases, 0.4, 0.6)

    ablation_weights = [0.0, 0.4, 0.5, 0.6, 0.7, 1.0]
    ablation_summary = []
    for sem_w in ablation_weights:
        kw_w = round(1.0 - sem_w, 2)
        if sem_w == 0.4:
            summary = baseline_summary
        else:
            _, summary = evaluate_weights(assistant, eval_cases, sem_w, kw_w)
        ablation_summary.append({
            "semantic_weight": sem_w,
            "keyword_weight": kw_w,
            "ALL": summary["ALL"],
        })

    lowest3 = sorted(
        baseline_per_query,
        key=lambda row: (row["metrics"]["mrr5"], row["metrics"]["ndcg5"], row["metrics"]["r5"]),
    )[:3]

    output = {
        "eval_set_size": len(eval_cases),
        "embedding_mode": "live_gemini" if using_live_gemini_embeddings else "offline_fallback",
        "baseline_weights": {"semantic": 0.4, "keyword": 0.6},
        "baseline_summary": baseline_summary,
        "ablation_sweep": ablation_summary,
        "lowest_3_queries": lowest3,
        "per_query": baseline_per_query,
    }
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    baseline_rows = [(k, baseline_summary[k]) for k in ("ALL", "en", "bm", "cross_en_to_bm", "cross_bm_to_en")]
    print_table("Baseline 40:60 Hybrid Retrieval Breakdown", baseline_rows, "Slice")

    ablation_rows = [
        (f"sem={a['semantic_weight']:.1f}/kw={a['keyword_weight']:.1f}", a["ALL"])
        for a in ablation_summary
    ]
    print_table("Weight Ablation Sweep (ALL Queries)", ablation_rows, "Weights")

    print("\n=== Top 3 Lowest-Scoring Queries (Baseline 40:60) ===")
    for idx, q in enumerate(lowest3, start=1):
        m = q["metrics"]
        print(f"{idx}. [{q['id']} | {q['direction']} | scope={q['scope']}] MRR@5={m['mrr5']:.4f} nDCG@5={m['ndcg5']:.4f} R@5={m['r5']:.4f}")
        print(f"   Query:     {q['query']}")
        print(f"   Expected:  {q['relevant_docs']}")
        print(f"   Retrieved: {q['retrieved_top5']}")

    print(f"\nSaved detailed results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
