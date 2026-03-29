"""
config.py — Central configuration for NUST Admission Assistant.
All paths are resolved relative to this file, so the project works
regardless of the current working directory.
"""
import os

# Absolute path to project root (wherever this file lives)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# ── Data directories ──────────────────────────────────────────────────────────
DATA_DIR       = os.path.join(PROJECT_ROOT, "data")
RAW_DIR        = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR  = os.path.join(DATA_DIR, "processed")
INDEX_DIR      = os.path.join(DATA_DIR, "index")

# ── Processed file paths ──────────────────────────────────────────────────────
QA_PAIRS_FILE  = os.path.join(PROCESSED_DIR, "qa_pairs.json")
CHUNKS_FILE    = os.path.join(PROCESSED_DIR, "chunks.json")
SYNONYMS_FILE  = os.path.join(PROCESSED_DIR, "synonyms.json")

# ── Index file paths ──────────────────────────────────────────────────────────
DOCUMENTS_FILE  = os.path.join(INDEX_DIR, "documents.json")
EMBEDDINGS_FILE = os.path.join(INDEX_DIR, "embeddings.npy")
BM25_FILE       = os.path.join(INDEX_DIR, "bm25.pkl")
QA_PAIRS_INDEX  = os.path.join(INDEX_DIR, "qa_pairs.json")
QA_EMBEDDINGS   = os.path.join(INDEX_DIR, "qa_embeddings.npy")

# ── Ollama settings ───────────────────────────────────────────────────────────
OLLAMA_BASE_URL  = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBEDDING_MODEL  = os.environ.get("EMBED_MODEL", "nomic-embed-text")
DEFAULT_LLM      = os.environ.get("LLM_MODEL", "llama3.2:3b")

# ── Test results ──────────────────────────────────────────────────────────────
TEST_RESULTS_DIR = os.path.join(PROJECT_ROOT, "test_results")
