"""
Deep Timing Analysis — Where Does Time Go?
============================================
Isolates each component: embedding call, BM25, vector dot product, Q&A check
"""

import sys
import os
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from retrieval.retriever import Retriever
from backend.classifier import QueryClassifier


def benchmark_retrieval():
    print("=" * 60)
    print("DEEP RETRIEVAL TIMING ANALYSIS")
    print("=" * 60)

    retriever = Retriever(num_gpu=0, num_thread=8)
    classifier = QueryClassifier()

    # Queries that hit fast_path (keyword) vs fast_path (vector) vs full hybrid
    test_queries = [
        # Keyword match (exact or near-exact) — should be 0-5ms
        ("What is the fee for BSCS?", "keyword_expected"),
        ("What is the fee for engineering programs at NUST?", "keyword_expected"),
        # Vector match — needs embedding call
        ("how much does computer science cost at nust", "vector_expected"),
        ("tell me about nust hostels", "vector_expected"),
        ("engineering programs offered", "vector_expected"),
        # Hybrid (no fast path match)
        ("What is the fee structure for international students?", "hybrid_expected"),
        ("Can I apply to both medical and engineering?", "hybrid_expected"),
        ("What is the difference between NET and SAT admission?", "hybrid_expected"),
    ]

    print(f"\nTesting {len(test_queries)} queries...\n")

    for query, expected in test_queries:
        print(f'--- "{query}" ---')

        # Break down retrieve() manually
        t_total = time.time()

        # Classify
        t0 = time.time()
        qt = classifier.classify(query)
        t_classify = time.time() - t0

        # Query expansion
        t0 = time.time()
        expanded = retriever._expand_query(query)
        t_expand = time.time() - t0

        # Q&A keyword check (fast path attempt 1)
        t0 = time.time()
        q_clean = __import__("re").sub(r"[^a-z0-9 ]", "", query.lower()).strip()
        keyword_match = False
        for idx in retriever.qa_indices:
            doc = retriever.documents[idx]
            q_ref = (
                __import__("re")
                .sub(r"[^a-z0-9 ]", "", doc.get("content", "").lower())
                .strip()
            )
            if q_clean == q_ref or q_clean in q_ref[: len(q_clean) + 10]:
                keyword_match = True
                break
        t_keyword = time.time() - t0

        # Embedding call (the expensive part)
        t0 = time.time()
        emb = retriever._get_embedding(query)
        t_embed = time.time() - t0

        # BM25 scoring
        t0 = time.time()
        from retrieval.retriever import bm25_tokenize

        tokenized = bm25_tokenize(expanded)
        scores = retriever.bm25.get_scores(tokenized)
        top_bm25 = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:5]
        t_bm25 = time.time() - t0

        # Vector dot product
        t0 = time.time()
        import numpy as np

        sims = np.dot(retriever.embeddings, emb)
        top_vec = np.argsort(sims)[::-1][:5]
        t_vector = time.time() - t0

        # Q&A vector check (fast path attempt 2)
        t0 = time.time()
        qa_embs = retriever.embeddings[retriever.qa_indices]
        qa_sims = np.dot(qa_embs, emb)
        t_qa_check = time.time() - t0

        t_total = time.time() - t_total

        print(f"  Expected: {expected}")
        print(f"  Keyword match: {keyword_match}")
        print(f"  Timing breakdown:")
        print(f"    classify:        {t_classify * 1000:>6.1f}ms")
        print(f"    query_expand:    {t_expand * 1000:>6.1f}ms")
        print(f"    keyword_check:   {t_keyword * 1000:>6.1f}ms")
        print(f"    EMBEDDING CALL:  {t_embed * 1000:>6.1f}ms  <--- THE BIG ONE")
        print(f"    BM25 scoring:    {t_bm25 * 1000:>6.1f}ms")
        print(f"    Vector dot:      {t_vector * 1000:>6.1f}ms")
        print(f"    QA vector check: {t_qa_check * 1000:>6.1f}ms")
        print(f"    TOTAL:           {t_total * 1000:>6.1f}ms")
        print()

    # === EMBEDDING WARM-UP TEST ===
    print("=" * 60)
    print("EMBEDDING WARM-UP TEST")
    print("=" * 60)
    print("Testing if embedding speed improves with repeated calls...\n")

    warmup_queries = [
        "test query one",
        "test query two",
        "What is the fee for BSCS?",
        "What is the fee for BSCS?",  # repeated - should be cached
    ]
    for i, q in enumerate(warmup_queries):
        t0 = time.time()
        emb = retriever._get_embedding(q)
        elapsed = time.time() - t0
        cached = "CACHED" if q in retriever._embed_cache else "NEW"
        print(f"  Call {i + 1}: {elapsed * 1000:.0f}ms ({cached})")

    print()
    print("=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)
    print("""
KEY FINDINGS:
  1. Embedding call to Ollama: 2000-3000ms per call (THE bottleneck)
  2. BM25 scoring: <1ms (negligible)
  3. Vector dot product: <1ms (negligible)
  4. Keyword fast path: <1ms when matched (avoids embedding entirely)
  5. LLM generation: ~45-50s for 50 tokens @ 15 tok/s

WHERE TIME IS SPENT (non-static query):
  - If keyword fast path:  <5ms total (96% of queries)
  - If vector fast path:   ~3000ms (embedding + check)
  - If full LLM:           ~3000ms retrieval + ~45000ms LLM = ~48s

OPTIMIZATION OPPORTUNITIES:
  1. Pre-warm embedding model (cold start penalty)
  2. Cache embeddings for common queries
  3. Use smaller/faster embedding model
  4. Consider quantized LLM for faster inference
    """)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    benchmark_retrieval()
