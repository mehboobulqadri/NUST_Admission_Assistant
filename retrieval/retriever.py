"""
NUST Admission Bot — Unified Retriever
=========================================
Loads pre-built indexes and provides hybrid search:
  - Q&A fast path (instant answers)
  - BM25 keyword search
  - Vector semantic search
  - Reciprocal Rank Fusion (RRF)

Usage:
    from retrieval.retriever import Retriever

    retriever = Retriever()
    results = retriever.retrieve("What is the fee for BSCS?")

    for r in results:
        print(r["score"], r["content"][:100])
"""

import os
import re
import sys
import json
import pickle
import numpy as np
import requests
from collections import defaultdict

# Allow importing config from any working directory
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_MODULE_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import (
    INDEX_DIR,
    PROCESSED_DIR,
    SYNONYMS_FILE,
    OLLAMA_BASE_URL,
    EMBEDDING_MODEL,
)

# ============================================================
# CONFIGURATION
# ============================================================
RETRIEVER_CONFIG = {
    "index_dir": INDEX_DIR,
    "ollama_url": OLLAMA_BASE_URL,
    "embedding_model": EMBEDDING_MODEL,
    # Search parameters
    "bm25_top_k": 5,  # candidates from BM25
    "vector_top_k": 10,  # candidates from vector search
    "final_top_k": 2,  # final results returned to LLM
    # Fusion weights (should sum to 1.0)
    "bm25_weight": 0.45,  # keyword matching (good for "BSCS", "fee")
    "vector_weight": 0.55,  # semantic matching (good for "how to apply")
    # Q&A fast path
    "qa_threshold": 0.70,  # similarity threshold for direct Q&A answer
    # RRF parameter (standard value, don't change unless testing)
    "rrf_k": 60,
}

# Synonym expansion for query understanding
SYNONYMS = {
    "cost": "fee",
    "price": "fee",
    "money": "fee",
    "charges": "fee",
    "tuition": "fee",
    "dues": "fee",
    "marks": "merit",
    "score": "merit",
    "cutoff": "merit",
    "aggregate": "merit",
    "percentage": "merit",
    "stay": "hostel",
    "dorm": "hostel",
    "room": "hostel",
    "accommodation": "hostel",
    "residence": "hostel",
    "courses": "programs",
    "subjects": "programs",
    "degree": "programs",
    "major": "programs",
    "apply": "admission",
    "register": "admission",
    "application": "admission",
    "enroll": "admission",
    "exam": "test",
    "examination": "test",
    "campus": "nust",
    "university": "nust",
}


# ============================================================
# BM25 TOKENIZER (must match build_index.py)
# ============================================================
BM25_STOPWORDS = {
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "shall",
    "can",
    "need",
    "a",
    "an",
    "and",
    "but",
    "or",
    "nor",
    "not",
    "so",
    "yet",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "they",
    "we",
    "our",
    "you",
    "your",
    "he",
    "she",
    "which",
    "who",
}


def bm25_tokenize(text):
    """Tokenize for BM25 — must match the tokenizer used during indexing."""
    words = re.findall(r"[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*", text.lower())
    return [w for w in words if w not in BM25_STOPWORDS and len(w) > 1]


# ============================================================
# RETRIEVER CLASS
# ============================================================
class Retriever:
    """
    Unified retriever with hybrid search.

    Architecture:
        Query → Expand → Q&A Check → BM25 + Vector → RRF Fusion → Top K
    """

    def __init__(self, config=None, num_gpu=None, num_thread=None):
        """Load all pre-built indexes into memory."""
        self.config = config or RETRIEVER_CONFIG
        self.num_gpu = num_gpu
        self.num_thread = num_thread
        index_dir = self.config["index_dir"]

        print("📚 Loading retrieval indexes...")

        # ---- Load documents ----
        docs_path = os.path.join(index_dir, "documents.json")
        with open(docs_path, "r", encoding="utf-8") as f:
            self.documents = json.load(f)

        # ---- Load embeddings ----
        emb_path = os.path.join(index_dir, "embeddings.npy")
        self.embeddings = np.load(emb_path)

        # ---- Load BM25 ----
        bm25_path = os.path.join(index_dir, "bm25.pkl")
        with open(bm25_path, "rb") as f:
            bm25_data = pickle.load(f)
            self.bm25 = bm25_data["bm25"]

        # ---- Identify Q&A pairs by index ----
        self.qa_indices = [
            i for i, doc in enumerate(self.documents) if doc.get("type") == "qa"
        ]

        # ---- Embedding cache (avoid re-embedding same query) ----
        self.cache_path = os.path.join(index_dir, "embed_cache.pkl")
        self._embed_cache = {}
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "rb") as f:
                    self._embed_cache = pickle.load(f)
            except Exception:
                pass

        # ---- Load synonyms ----
        if os.path.exists(SYNONYMS_FILE):
            with open(SYNONYMS_FILE, "r", encoding="utf-8") as f:
                self.synonyms = json.load(f)
        else:
            self.synonyms = SYNONYMS

        # ---- Stats ----
        num_qa = len(self.qa_indices)
        num_chunks = len(self.documents) - num_qa
        print(f"   ✅ Loaded: {num_chunks} chunks + {num_qa} Q&A pairs")
        print(f"   ✅ Embedding dim: {self.embeddings.shape[1]}")

        if self.num_gpu == 0:
            thread_info = f" (Threads: {self.num_thread})" if self.num_thread else ""
            print(f"   ⚠️ Forced CPU Mode for Embeddings{thread_info}")

        print(f"   ✅ Retriever ready!\n")

    def _detect_level(self, query):
        """
        Detect if query is about UG or PG programs.
        Returns "ug", "pg", or "both".
        """
        q = query.lower()

        ug_signals = [
            "bscs",
            "bsse",
            "bsee",
            "bsme",
            "bsce",
            "bsai",
            "bba",
            "bs ",
            "be ",
            "b.arch",
            "bachelor",
            "undergraduate",
            "fsc",
            "matric",
            "intermediate",
            "hssc",
            "ssc",
            "a-level",
            "a level",
            "o-level",
            "o level",
            "ibcc",
            "net test",
            "net ",
            "entry test",
            "12th",
            "pre-eng",
            "pre eng",
            "pre-med",
            "pre med",
            "ics",
            "dae",
            "llb",
            "architecture",
            "industrial design",
            "bioinformatics",
            "bs data",
            "bs artificial",
            "bs computer",
            "bs economics",
            "bs psychology",
            "bs mass",
            "bs english",
            "bs physics",
            "bs math",
            "bs chem",
            "bs biotech",
            "bs food",
            "bs agriculture",
            "bs accounting",
            "bs tourism",
            "bs public",
        ]

        pg_signals = [
            "ms ",
            "mba",
            "emba",
            "phd",
            "masters",
            "master's",
            "postgraduate",
            "post graduate",
            "post-graduate",
            "gat",
            "gre",
            "gnet",
            "hat test",
            "research",
            "thesis",
            "supervisor",
            "18 years",
            "16 years",
        ]

        ug_score = sum(1 for s in ug_signals if s in q)
        pg_score = sum(1 for s in pg_signals if s in q)

        if ug_score > pg_score:
            return "ug"
        elif pg_score > ug_score:
            return "pg"
        return "both"

    # ==========================================================
    # MAIN RETRIEVE METHOD
    # ==========================================================
    def retrieve(self, query, top_k=None):
        # Optimization: Use 3 sources on CPU for better accuracy
        default_top_k = 3 if self.num_gpu == 0 else self.config["final_top_k"]
        top_k = top_k or default_top_k

        expanded_query = self._expand_query(query)

        # Track embedding for reuse between Q&A check and vector search
        cached_embedding = None

        qa_result, cached_embedding = self._qa_fast_path(query)
        if qa_result is not None:
            return [qa_result]

        bm25_results = self._bm25_search(expanded_query)
        vector_results = self._vector_search(query, cached_embedding=cached_embedding)
        fused_results = self._rrf_fusion(bm25_results, vector_results)

        # Demote PG results for UG queries (default is UG)
        level = self._detect_level(query)
        if level == "ug" or level == "both":
            fused_results = self._demote_pg(fused_results)

        return fused_results[:top_k]

    def _filter_by_level(self, results, level):
        """Demote results that don't match the detected level."""
        filtered = []
        demoted = []

        for r in results:
            content = r.get("content", "").lower()
            source = r.get("source", "").lower()

            is_pg = any(
                w in content or w in source
                for w in [
                    "masters",
                    "ms ",
                    "mba",
                    "phd",
                    "gat",
                    "gre",
                    "postgraduate",
                    "masters faq",
                ]
            )
            is_ug = any(
                w in content or w in source
                for w in [
                    "undergraduate",
                    "net test",
                    "entry test",
                    "bachelor",
                    "bs ",
                    "be ",
                    "bba",
                    "fsc",
                ]
            )

            if level == "ug" and is_pg and not is_ug:
                demoted.append(r)
            elif level == "pg" and is_ug and not is_pg:
                demoted.append(r)
            else:
                filtered.append(r)

        # Return filtered first, then demoted as fallback
        return filtered + demoted

    def _demote_pg(self, results):
        """Push Masters FAQ results to the bottom."""
        ug_results = []
        pg_results = []

        for r in results:
            source = r.get("source", "").lower()
            content = r.get("content", "").lower()

            is_masters_faq = (
                "masters faq" in source
                or "masters program" in content
                or "ms section" in content
                or "ms admission" in content
                or ("gat" in content and "general" in content)
                or "pgadmission" in content
            )

            if is_masters_faq:
                pg_results.append(r)
            else:
                ug_results.append(r)

        return ug_results + pg_results

    # ==========================================================
    # QUERY EXPANSION
    # ==========================================================
    def _expand_query(self, query):
        """
        Add synonyms to the query for better BM25 recall.

        "What is the cost of BSCS?"
        → "What is the cost fee of BSCS?"

        This helps BM25 find chunks containing "fee" even when
        the user typed "cost".
        """
        words = query.lower().split()
        expanded = list(words)

        for word in words:
            clean_word = re.sub(r"[^a-z]", "", word)
            if clean_word in self.synonyms:
                synonym = self.synonyms[clean_word]
                if synonym not in expanded:
                    expanded.append(synonym)

        return " ".join(expanded)

    # ==========================================================
    # Q&A FAST PATH
    # ==========================================================
    def _qa_fast_path(self, query):
        if not self.qa_indices:
            return None, None

        # Micro-Optimization: Keyword-based early exit (Saves ~500ms embedding time)
        q_clean = re.sub(r"[^a-z0-9 ]", "", query.lower()).strip()
        for idx in self.qa_indices:
            doc = self.documents[idx]
            q_ref = re.sub(r"[^a-z0-9 ]", "", doc.get("content", "").lower()).strip()
            # If the query IS the question (simple), return it instantly
            if q_clean == q_ref or q_clean in q_ref[: len(q_clean) + 10]:
                return {
                    "content": doc.get("answer", doc.get("content", "")),
                    "source": doc.get("source", ""),
                    "score": 1.0,
                    "method": "fast_path_keyword",
                }, None

        query_emb = self._get_embedding(query)
        qa_embeddings = self.embeddings[self.qa_indices]
        similarities = np.dot(qa_embeddings, query_emb)

        top_k = min(5, len(self.qa_indices))
        top_local_indices = np.argsort(similarities)[::-1][:top_k]

        for local_idx in top_local_indices:
            score = float(similarities[local_idx])
            if score < self.config["qa_threshold"]:
                break

            doc_idx = self.qa_indices[local_idx]
            doc = self.documents[doc_idx]
            answer = doc.get("answer", doc.get("content", ""))

            # Skip garbage answers that just link to websites
            answer_lower = answer.lower()
            if any(
                skip in answer_lower
                for skip in [
                    "visit our website",
                    "visit the website",
                    "please visit",
                    "click here",
                    "following link",
                    "< ",
                    "may be accessed through the link",
                    "can be found on",
                    "details regarding",
                    "> ",
                ]
            ):
                continue

            # Skip very short answers (under 50 chars = probably not useful)
            if len(answer.strip()) < 50:
                continue

            return {
                "content": answer,
                "source": doc.get("source", ""),
                "score": score,
                "category": doc.get("category", ""),
                "method": "fast_path",
                "type": "qa",
            }, query_emb

        return None, query_emb

    # ==========================================================
    # BM25 KEYWORD SEARCH
    # ==========================================================
    def _bm25_search(self, query):
        """
        BM25 keyword search.

        Excellent for:
        - Specific terms: "BSCS", "SEECS", "NET"
        - Exact matches: "fee structure", "hostel"

        Returns ranked results with BM25 scores.
        """
        top_k = self.config["bm25_top_k"]
        tokenized_query = bm25_tokenize(query)

        if not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for rank, idx in enumerate(top_indices):
            idx = int(idx)
            if scores[idx] <= 0:
                continue

            doc = self.documents[idx]
            results.append(
                {
                    "doc_index": idx,
                    "content": doc.get("content", ""),
                    "source": doc.get("source", ""),
                    "score": float(scores[idx]),
                    "category": doc.get("category", ""),
                    "type": doc.get("type", "chunk"),
                    "method": "bm25",
                    "rank": rank,
                }
            )

        return results

    # ==========================================================
    # VECTOR SEMANTIC SEARCH
    # ==========================================================
    def _vector_search(self, query, cached_embedding=None):
        """
        Cosine similarity search using embeddings.

        Excellent for:
        - Paraphrased questions: "How do I get in?" → finds "admission process"
        - Conceptual queries: "financial help" → finds "scholarships"

        Returns ranked results with similarity scores.
        """
        top_k = self.config["vector_top_k"]

        query_emb = (
            cached_embedding
            if cached_embedding is not None
            else self._get_embedding(query)
        )
        similarities = np.dot(self.embeddings, query_emb)
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for rank, idx in enumerate(top_indices):
            idx = int(idx)
            doc = self.documents[idx]
            results.append(
                {
                    "doc_index": idx,
                    "content": doc.get("content", ""),
                    "source": doc.get("source", ""),
                    "score": float(similarities[idx]),
                    "category": doc.get("category", ""),
                    "type": doc.get("type", "chunk"),
                    "method": "vector",
                    "rank": rank,
                }
            )

        return results

    # ==========================================================
    # RECIPROCAL RANK FUSION (RRF)
    # ==========================================================
    def _rrf_fusion(self, bm25_results, vector_results):
        """
        Combine BM25 and vector results using Reciprocal Rank Fusion.

        RRF formula: score(doc) = Σ (weight / (k + rank))

        Why RRF instead of simple score averaging?
        - BM25 scores and cosine similarities are on different scales
        - RRF uses RANK position, which is scale-independent
        - Used by Elasticsearch, Pinecone, and most production systems
        """
        k = self.config["rrf_k"]
        bm25_w = self.config["bm25_weight"]
        vector_w = self.config["vector_weight"]

        fused_scores = defaultdict(float)
        doc_map = {}

        # Score BM25 results by rank
        for result in bm25_results:
            doc_idx = result["doc_index"]
            fused_scores[doc_idx] += bm25_w * (1.0 / (k + result["rank"]))
            doc_map[doc_idx] = result

        # Score vector results by rank
        for result in vector_results:
            doc_idx = result["doc_index"]
            fused_scores[doc_idx] += vector_w * (1.0 / (k + result["rank"]))
            if doc_idx not in doc_map:
                doc_map[doc_idx] = result

        # Sort by fused score
        sorted_indices = sorted(
            fused_scores.keys(),
            key=lambda x: fused_scores[x],
            reverse=True,
        )

        # Build final results
        results = []
        for idx in sorted_indices:
            result = doc_map[idx].copy()
            result["score"] = round(fused_scores[idx], 6)
            result["method"] = "hybrid"
            # Remove internal rank field
            result.pop("rank", None)
            result.pop("doc_index", None)
            results.append(result)

        return results

    # ==========================================================
    # EMBEDDING HELPER
    # ==========================================================
    def _get_embedding(self, text):
        if text in self._embed_cache:
            return self._embed_cache[text]

        options = {}
        if self.num_gpu is not None:
            options["num_gpu"] = self.num_gpu
        if self.num_thread is not None:
            options["num_thread"] = self.num_thread

        try:
            # Try new endpoint first
            try:
                payload = {
                    "model": self.config["embedding_model"],
                    "input": [text],
                }
                if options:
                    payload["options"] = options

                response = requests.post(
                    f"{self.config['ollama_url']}/api/embed",
                    json=payload,
                    timeout=30,
                )
                response.raise_for_status()
                embedding = np.array(response.json()["embeddings"][0], dtype=np.float32)
            except (requests.HTTPError, KeyError, IndexError):
                # Fallback to old endpoint
                payload = {
                    "model": self.config["embedding_model"],
                    "prompt": text,
                }
                if options:
                    payload["options"] = options

                response = requests.post(
                    f"{self.config['ollama_url']}/api/embeddings",
                    json=payload,
                    timeout=30,
                )
                response.raise_for_status()
                embedding = np.array(response.json()["embedding"], dtype=np.float32)

            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            self._embed_cache[text] = embedding
            try:
                with open(self.cache_path, "wb") as f:
                    pickle.dump(self._embed_cache, f)
            except Exception:
                pass
            return embedding

        except requests.ConnectionError:
            print("Cannot reach Ollama. Is it running?")
            raise


# ============================================================
# TEST FUNCTION — Run this to verify everything works
# ============================================================
def test_retriever():
    """Quick test to verify the retriever works."""
    print("=" * 60)
    print("🧪 RETRIEVER TEST")
    print("=" * 60)

    retriever = Retriever()

    test_queries = [
        "What is the fee for BSCS?",
        "How do I apply to NUST?",
        "What is the aggregate formula?",
        "Tell me about hostel facilities",
        "What programs does SEECS offer?",
        "NET test dates and pattern",
        "Scholarship opportunities at NUST",
    ]

    for query in test_queries:
        print(f"\n{'─' * 50}")
        print(f"📝 Query: {query}")
        print(f"{'─' * 50}")

        results = retriever.retrieve(query, top_k=3)

        if not results:
            print("   ⚠️ No results found")
            continue

        for i, result in enumerate(results):
            method_icon = "⚡" if result["method"] == "fast_path" else "🔍"
            print(
                f"\n   {method_icon} Result {i + 1} "
                f"[{result['method']}] "
                f"(score: {result['score']:.4f}) "
                f"[{result['category']}]"
            )
            # Show first 150 chars of content
            content_preview = result["content"][:150].replace("\n", " ")
            print(f"   📄 {content_preview}...")
            print(f"   📌 Source: {result['source']}")

    print(f"\n{'=' * 60}")
    print("✅ Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_retriever()
