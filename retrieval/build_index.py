"""
NUST Admission Bot — Index Builder
====================================
Reads processed chunks + Q&A pairs → generates embeddings via Ollama
→ builds BM25 index → saves everything for fast retrieval.

Run ONCE after processing data:
    python retrieval/build_index.py

Prerequisites:
    - Ollama running with nomic-embed-text pulled
    - data/processed/chunks.json exists
    - pip install rank_bm25 numpy requests
"""

import os
import sys
import json
import time
import pickle
import numpy as np
import requests

# Allow importing config from any working directory
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_MODULE_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import (
    PROCESSED_DIR, INDEX_DIR, QA_PAIRS_FILE, CHUNKS_FILE,
    OLLAMA_BASE_URL, EMBEDDING_MODEL
)

# ============================================================
# CONFIGURATION (kept as dict for backward compat, values from config.py)
# ============================================================
CONFIG = {
    "processed_dir": PROCESSED_DIR,
    "index_dir": INDEX_DIR,
    "ollama_url": OLLAMA_BASE_URL,
    "embedding_model": EMBEDDING_MODEL,
}


# ============================================================
# OLLAMA EMBEDDING CLIENT
# ============================================================
class OllamaEmbedder:
    def __init__(self, base_url=None, model=None):
        self.base_url = base_url or CONFIG["ollama_url"]
        self.model = model or CONFIG["embedding_model"]
        self.dimension = None

    def check_connection(self):
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]
            found = any(
                self.model in name or name.startswith(self.model)
                for name in model_names
            )
            if not found:
                print(f"Model '{self.model}' not found. Available: {model_names}")
                print(f"Run: ollama pull {self.model}")
                return False
            print(f"Ollama connected. Model '{self.model}' ready.")
            return True
        except requests.ConnectionError:
            print("Cannot connect to Ollama. Run: ollama serve")
            return False

    def embed_batch(self, texts, batch_size=128, show_progress=True):
        """Embed texts using real batching via /api/embed endpoint."""
        embeddings = []
        total = len(texts)
        start_time = time.time()

        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            # Truncate long texts
            batch = [t[:8000] if len(t) > 8000 else t for t in batch]

            try:
                # Try new /api/embed endpoint (supports batching)
                response = requests.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": batch},
                    timeout=120,
                )
                response.raise_for_status()
                result = response.json()
                batch_embeddings = result.get("embeddings", [])

            except (requests.HTTPError, KeyError):
                # Fallback to old endpoint one-by-one
                batch_embeddings = []
                for text in batch:
                    resp = requests.post(
                        f"{self.base_url}/api/embeddings",
                        json={"model": self.model, "prompt": text},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    batch_embeddings.append(resp.json()["embedding"])

            embeddings.extend(batch_embeddings)

            if self.dimension is None and embeddings:
                self.dimension = len(embeddings[0])

            if show_progress:
                done = min(i + batch_size, total)
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                remaining = (total - done) / rate if rate > 0 else 0
                print(
                    f"   Embedded {done}/{total} "
                    f"({rate:.1f}/sec, ~{remaining:.0f}s remaining)"
                )

        elapsed = time.time() - start_time
        print(f"   All {total} embeddings done in {elapsed:.1f}s")
        return embeddings

# ============================================================
# BM25 INDEX BUILDER
# ============================================================
class BM25Builder:
    """Build BM25 keyword search index."""

    # Extended stopwords for better BM25
    STOPWORDS = {
        "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "need",
        "a", "an", "and", "but", "or", "nor", "not", "so", "yet",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after",
        "here", "there", "when", "where", "why", "how", "all",
        "this", "that", "these", "those", "it", "its", "they",
        "we", "our", "you", "your", "he", "she", "which", "who",
    }

    @classmethod
    def tokenize(cls, text):
        """
        Tokenize text for BM25 — lowercase, remove stopwords,
        keep meaningful terms.
        """
        import re
        # Extract words (including hyphenated and abbreviated)
        words = re.findall(r'[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*', text.lower())
        # Remove stopwords and very short tokens
        return [w for w in words if w not in cls.STOPWORDS and len(w) > 1]

    @classmethod
    def build(cls, texts):
        """Build BM25 index from list of texts."""
        from rank_bm25 import BM25Okapi

        print("   Tokenizing corpus...")
        tokenized_corpus = [cls.tokenize(text) for text in texts]

        print("   Building BM25 index...")
        bm25 = BM25Okapi(tokenized_corpus)

        return bm25, tokenized_corpus


# ============================================================
# MAIN INDEX BUILDER
# ============================================================
def build_index():
    """
    Main function: loads data, generates embeddings, builds indexes.
    """
    print("=" * 60)
    print("🔨 NUST Admission Bot — Index Builder")
    print("=" * 60)

    # ----------------------------------------------------------
    # Step 1: Check Ollama
    # ----------------------------------------------------------
    print("\n📡 Step 1: Checking Ollama connection...")
    embedder = OllamaEmbedder()
    if not embedder.check_connection():
        sys.exit(1)

    # ----------------------------------------------------------
    # Step 2: Load processed data
    # ----------------------------------------------------------
    print("\n📦 Step 2: Loading processed data...")

    chunks_path = os.path.join(CONFIG["processed_dir"], "chunks.json")
    qa_path = os.path.join(CONFIG["processed_dir"], "qa_pairs.json")

    if not os.path.exists(chunks_path):
        print(f"❌ Not found: {chunks_path}")
        print("   Run process_everything.py first!")
        sys.exit(1)

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    qa_pairs = []
    if os.path.exists(qa_path):
        with open(qa_path, "r", encoding="utf-8") as f:
            qa_pairs = json.load(f)
    else:
        print("   ⚠️ No qa_pairs.json found. Continuing without Q&A fast path.")

    print(f"   Loaded {len(chunks)} chunks + {len(qa_pairs)} Q&A pairs")

    # ----------------------------------------------------------
    # Step 3: Combine into unified document list
    # ----------------------------------------------------------
    # Q&A pairs go first so we can quickly identify them by index
    all_documents = qa_pairs + chunks

    # Prepare texts for embedding
    texts_for_embedding = []
    for doc in all_documents:
        if doc.get("type") == "qa":
            # For Q&A, embed question + answer combined
            # This catches both "What is the fee?" and content about fees
            text = doc.get("content", "")
            if not text:
                text = doc.get("question", "") + " " + doc.get("answer", "")
        else:
            text = doc.get("content", "")

        texts_for_embedding.append(text)

    print(f"   Total documents to index: {len(all_documents)}")

    # ----------------------------------------------------------
    # Step 4: Generate embeddings
    # ----------------------------------------------------------
    print(f"\n🧠 Step 3: Generating embeddings...")
    print(f"   Model: {CONFIG['embedding_model']}")
    print(f"   Documents: {len(texts_for_embedding)}")
    est_time = len(texts_for_embedding) * 0.1
    print(f"   Estimated time: ~{est_time:.0f} seconds")

    embeddings = embedder.embed_batch(texts_for_embedding)

    # Convert to numpy and normalize for cosine similarity
    embeddings_array = np.array(embeddings, dtype=np.float32)
    norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings_normalized = embeddings_array / norms

    print(f"   Embedding dimension: {embeddings_normalized.shape[1]}")

    # ----------------------------------------------------------
    # Step 5: Build BM25 index
    # ----------------------------------------------------------
    print(f"\n📊 Step 4: Building BM25 index...")
    bm25, tokenized_corpus = BM25Builder.build(texts_for_embedding)
    print(f"   ✅ BM25 index built")

    # ----------------------------------------------------------
    # Step 6: Save everything
    # ----------------------------------------------------------
    print(f"\n💾 Step 5: Saving indexes...")
    index_dir = CONFIG["index_dir"]
    os.makedirs(index_dir, exist_ok=True)

    # Save embeddings (numpy)
    emb_path = os.path.join(index_dir, "embeddings.npy")
    np.save(emb_path, embeddings_normalized)
    emb_size = os.path.getsize(emb_path) / (1024 * 1024)
    print(f"   ✅ Embeddings:  {emb_path} ({emb_size:.1f} MB)")

    # Save documents (JSON)
    docs_path = os.path.join(index_dir, "documents.json")
    with open(docs_path, "w", encoding="utf-8") as f:
        json.dump(all_documents, f, indent=2, ensure_ascii=False)
    print(f"   ✅ Documents:   {docs_path}")

    # Save BM25 index (pickle)
    bm25_path = os.path.join(index_dir, "bm25.pkl")
    with open(bm25_path, "wb") as f:
        pickle.dump({"bm25": bm25, "tokenized": tokenized_corpus}, f)
    print(f"   ✅ BM25 index:  {bm25_path}")

    # Save metadata
    meta = {
        "total_documents": len(all_documents),
        "num_qa_pairs": len(qa_pairs),
        "num_chunks": len(chunks),
        "embedding_dim": int(embeddings_normalized.shape[1]),
        "embedding_model": CONFIG["embedding_model"],
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    meta_path = os.path.join(index_dir, "index_config.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"   ✅ Config:      {meta_path}")

    # ----------------------------------------------------------
    # Done!
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print("🎉 INDEX BUILT SUCCESSFULLY")
    print("=" * 60)
    print(f"   Total documents:  {meta['total_documents']}")
    print(f"   Q&A pairs:        {meta['num_qa_pairs']}")
    print(f"   Chunks:           {meta['num_chunks']}")
    print(f"   Embedding dim:    {meta['embedding_dim']}")
    print(f"   Index location:   {index_dir}/")
    print()
    print("   Next: Use retrieval/retriever.py to search!")
    print("=" * 60)


if __name__ == "__main__":
    build_index()