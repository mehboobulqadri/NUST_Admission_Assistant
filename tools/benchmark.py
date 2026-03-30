"""
Full Pipeline Benchmark — llama3.2:3b CPU
==========================================
Measures timing at every stage: classify, facts, retrieval, prompt, LLM
"""

import sys
import os
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from llm.ollama_client import OllamaLLM
from llm.prompt_builder import PromptBuilder
from llm.response_formatter import ResponseFormatter
from retrieval.retriever import Retriever
from backend.classifier import QueryClassifier, STATIC

# === TEST QUERIES ===
test_queries = [
    # Fast path (should bypass LLM entirely)
    ("What is the fee for BSCS?", "fast_path"),
    ("What is the fee for engineering?", "fast_path"),
    ("What is the fee for electrical engineering?", "fast_path"),
    # Fact injection queries (classifier extracts hardcoded facts)
    ("What is the aggregate formula for NUST?", "fact_injection"),
    ("What are the important dates?", "fact_injection"),
    ("How many marks are needed for NUST admission?", "fact_injection"),
    # Static responses (no LLM, no retrieval)
    ("Hello", "static"),
    ("Who are you?", "static"),
    # Full LLM queries (retrieve + LLM)
    ("How do I apply to NUST?", "llm"),
    ("Does NUST have hostels?", "llm"),
    ("What programs does SEECS offer?", "llm"),
    ("Is ICS student eligible for engineering?", "llm"),
    # Urdu / casual
    ("NET test kab hai?", "llm"),
]


def main():
    print("=" * 60)
    print("BENCHMARKING FULL PIPELINE — llama3.2:3b CPU")
    print("=" * 60)

    # === INIT ===
    print("\nInitializing components...")
    t0 = time.time()
    classifier = QueryClassifier()
    print(f"  Classifier: {time.time() - t0:.2f}s")

    t0 = time.time()
    retriever = Retriever(num_gpu=0, num_thread=8)
    print(f"  Retriever:  {time.time() - t0:.2f}s")

    t0 = time.time()
    llm = OllamaLLM(
        model="llama3.2:3b",
        temperature=0.3,
        num_ctx=2048,
        num_gpu=0,
        num_thread=8,
    )
    print(f"  LLM init:   {time.time() - t0:.2f}s")

    prompt_builder = PromptBuilder(use_distilled=True)
    formatter = ResponseFormatter()

    if not llm.check_connection():
        print("ERROR: Cannot connect to LLM")
        sys.exit(1)

    print(f"\nRunning {len(test_queries)} queries...\n")

    results = []
    total_wall = 0

    for query, expected_type in test_queries:
        print(f'--- Query: "{query}" (expected: {expected_type}) ---')
        timings = {}
        t_start = time.time()

        # Step 1: Classify
        t0 = time.time()
        query_type = classifier.classify(query)
        timings["classify"] = time.time() - t0

        if query_type in STATIC:
            response = STATIC[query_type]
            timings["total"] = time.time() - t_start
            timings["path"] = "static"
            timings["llm"] = 0
            timings["retrieval"] = 0
            timings["extract_facts"] = 0
            timings["prompt_build"] = 0
            print(f"  Path: STATIC")
            print(f"  Response: {response[:100]}")
            print(
                f"  Timing: classify={timings['classify'] * 1000:.0f}ms total={timings['total'] * 1000:.0f}ms"
            )
            results.append({"query": query, "type": query_type, "timings": timings})
            total_wall += timings["total"]
            print()
            continue

        # Step 2: Extract facts
        t0 = time.time()
        injected_facts = classifier.extract_facts(query)
        timings["extract_facts"] = time.time() - t0

        # Step 3: Retrieve
        t0 = time.time()
        retrieved = retriever.retrieve(query, top_k=3)
        timings["retrieval"] = time.time() - t0
        retriever_method = (
            retrieved[0].get("method", "unknown") if retrieved else "none"
        )

        # Check if fast path
        is_fast_path = len(retrieved) == 1 and retrieved[0].get("method") in [
            "fast_path",
            "fast_path_keyword",
        ]

        if is_fast_path:
            answer = retrieved[0]["content"]
            timings["llm"] = 0
            timings["prompt_build"] = 0
            timings["total"] = time.time() - t_start
            timings["path"] = "fast_path"
            print(f"  Path: FAST_PATH")
            print(
                f"  Retrieval method: {retriever_method} (score: {retrieved[0]['score']:.4f})"
            )
            print(f"  Response: {answer[:120]}...")
            print(f"  Facts injected: {bool(injected_facts)}")
            print(
                f"  Timing: classify={timings['classify'] * 1000:.0f}ms "
                f"retrieve={timings['retrieval'] * 1000:.0f}ms "
                f"total={timings['total'] * 1000:.0f}ms"
            )
            results.append({"query": query, "type": query_type, "timings": timings})
            total_wall += timings["total"]
            print()
            continue

        # Step 4: Build prompt
        t0 = time.time()
        prompt, system_prompt, sources = prompt_builder.build(
            query=query,
            retrieved_results=retrieved,
            injected_facts=injected_facts,
        )
        timings["prompt_build"] = time.time() - t0

        # Step 5: LLM generate
        t0 = time.time()
        llm_result = llm.generate(prompt, system_prompt)
        timings["llm"] = time.time() - t0

        timings["total"] = time.time() - t_start
        timings["path"] = "llm"

        answer_text = llm_result.get("text", "")
        tok_per_sec = llm_result.get("tokens_per_second", 0)
        tokens_gen = llm_result.get("tokens_generated", 0)
        error = llm_result.get("error")

        # Format
        formatted = formatter.format(
            answer_text=answer_text,
            sources=sources,
            method="hybrid",
            response_time=timings["total"],
            tokens_per_second=tok_per_sec,
        )

        print(f"  Path: LLM")
        print(f"  Query type: {query_type}")
        print(f"  Facts injected: {bool(injected_facts)}")
        print(f"  Retrieved: {len(retrieved)} docs, method={retriever_method}")
        if injected_facts:
            print(f"  FACTS: {injected_facts[:80]}...")
        print(f"  Response: {answer_text[:150]}...")
        if error:
            print(f"  ERROR: {error}")
        print(f"  Tokens: {tokens_gen} @ {tok_per_sec:.1f} tok/s")
        print(f"  Timing:")
        print(f"    classify:      {timings['classify'] * 1000:>6.0f}ms")
        print(f"    extract_facts: {timings.get('extract_facts', 0) * 1000:>6.0f}ms")
        print(f"    retrieval:     {timings['retrieval'] * 1000:>6.0f}ms")
        print(f"    prompt_build:  {timings['prompt_build'] * 1000:>6.0f}ms")
        print(f"    LLM generate:  {timings['llm'] * 1000:>6.0f}ms")
        print(f"    TOTAL:         {timings['total'] * 1000:>6.0f}ms")
        results.append(
            {
                "query": query,
                "type": query_type,
                "timings": timings,
                "tok_s": tok_per_sec,
                "response": answer_text[:100],
            }
        )
        total_wall += timings["total"]
        print()

    # === SUMMARY ===
    print("=" * 60)
    print("TIMING SUMMARY")
    print("=" * 60)

    static_times = [
        r["timings"]["total"] for r in results if r["timings"].get("path") == "static"
    ]
    fast_times = [
        r["timings"]["total"]
        for r in results
        if r["timings"].get("path") == "fast_path"
    ]
    llm_times = [
        r["timings"]["total"] for r in results if r["timings"].get("path") == "llm"
    ]
    retrieval_times = [
        r["timings"]["retrieval"]
        for r in results
        if r["timings"].get("path") != "static"
    ]
    llm_gen_times = [
        r["timings"]["llm"] for r in results if r["timings"].get("path") == "llm"
    ]

    if static_times:
        print(
            f"  Static responses:  avg={sum(static_times) / len(static_times) * 1000:.0f}ms  (n={len(static_times)})"
        )
    if fast_times:
        print(
            f"  Fast path:         avg={sum(fast_times) / len(fast_times) * 1000:.0f}ms  (n={len(fast_times)})"
        )
    if llm_times:
        print(
            f"  Full LLM:          avg={sum(llm_times) / len(llm_times) * 1000:.0f}ms  (n={len(llm_times)})"
        )
    if retrieval_times:
        print(
            f"  Retrieval avg:     {sum(retrieval_times) / len(retrieval_times) * 1000:.0f}ms"
        )
    if llm_gen_times:
        print(
            f"  LLM generation avg:{sum(llm_gen_times) / len(llm_gen_times) * 1000:.0f}ms"
        )

    tok_s_vals = [r.get("tok_s", 0) for r in results if r.get("tok_s", 0) > 0]
    if tok_s_vals:
        print(f"  Avg tok/s:         {sum(tok_s_vals) / len(tok_s_vals):.1f}")

    print(f"  Total wall time:   {total_wall:.1f}s")
    print()

    # === RESPONSE QUALITY CHECK ===
    print("=" * 60)
    print("RESPONSE QUALITY CHECK")
    print("=" * 60)
    for r in results:
        path = r["timings"].get("path", "?")
        resp = r.get("response", "")
        if path == "llm":
            issues = []
            if "Fact:" in resp:
                issues.append("LEAKS 'Fact:' prefix")
            if "Yes," in resp and "No," in resp:
                issues.append("CONTRADICTORY Yes/No")
            if "I don't have" in resp and r.get("query", "").lower() not in [
                "who is the prime minister"
            ]:
                issues.append("REFUSED despite context")
            if issues:
                print(f'  ISSUE: "{r["query"]}" -> {", ".join(issues)}')
    print("=" * 60)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
