# AGENTS.md — Contributor Guide

## Project Overview

A **local RAG chatbot** for NUST (National University of Sciences & Technology) undergraduate admissions. Runs 100% offline via Ollama. Hybrid retrieval: BM25 + vector embeddings (nomic-embed-text) with Reciprocal Rank Fusion.

**Stack:** Python 3.10+, FastAPI (web UI), Ollama (LLM inference), numpy, rank-bm25, pdfplumber, Gradio (legacy).

---

## Build / Run / Test Commands

```bash
# Setup (uses uv package manager)
uv sync                                    # Install dependencies into .venv

# Run the web app
uv run ui/app.py                           # FastAPI server at http://localhost:8000
uv run ui/app.py --model llama3.2:3b --cpu # CPU-only mode with specific model

# Rebuild knowledge base (after updating data/raw/ PDFs)
uv run knowledge/process_data.py           # Parse PDFs → chunks + QA pairs
uv run retrieval/build_index.py            # Build BM25 + vector indexes

# Test suite (custom scripts, no pytest)
uv run python tools/test_suite.py --fast                           # Retrieval-only test (~30s)
uv run python tools/test_suite.py                                  # Full LLM test, default model (~15min)
uv run python tools/test_suite.py --model llama3.2:3b              # Full test, specific model
uv run python tools/test_suite.py --fast --sample 3                # Sample 3 questions per category
uv run python tools/test_suite.py --cpu                            # Force CPU-only mode
uv run python tools/evaluate_all.py                                # Run across all local Ollama models
uv run python tools/evaluate_parallel.py                           # Parallel evaluation

# Other tools
uv run python tools/analyze_suite.py       # Analyze past test results
uv run python tools/generate_summary.py    # Generate summary from results
uv run python tools/debug_chunks.py        # Inspect processed chunks
uv run python tools/extract_faqs.py        # Extract FAQ pairs from docs
uv run python tools/rebuild_qa_pairs.py    # Rebuild QA pair index
uv run python tools/add_structured_qa.py   # Add structured QA entries
```

**Running a single test category:** Edit `tools/test_suite.py` or pass `--sample 1` to run a minimal set. There is no single-test runner; the suite runs all categories at once.

---

## Architecture

```
User Query
  → backend/classifier.py    (classify: greeting | static | query | offtopic | sensitive)
  → retrieval/retriever.py   (hybrid BM25 + vector search, Q&A fast path)
  → llm/prompt_builder.py    (build prompt with context + facts)
  → llm/ollama_client.py     (Ollama /api/generate, streaming)
  → llm/response_formatter.py (clean output, strip think tags)
  → ui/app.py                (FastAPI SSE streaming to frontend)
```

Key files:
- `config.py` — all paths and Ollama settings (env vars: `OLLAMA_URL`, `EMBED_MODEL`, `LLM_MODEL`)
- `backend/classifier.py` — query classification, static answers, Urdu/typo handling
- `backend/settings.py` — runtime-tunable settings via dataclasses
- `retrieval/retriever.py` — unified retriever with BM25, vector, RRF fusion
- `llm/ollama_client.py` — Ollama wrapper with streaming and caching
- `llm/prompt_builder.py` — full and distilled (CPU) system prompts
- `llm/response_formatter.py` — output cleaning (Qwen think tags, leakage, contradictions)
- `ui/app.py` — FastAPI app with SSE chat endpoint, settings API, model switching

---

## Code Style

### Imports
- Standard library first, then third-party, then local — separated by blank lines.
- Use `sys.path.insert(0, ...)` at module top for cross-package imports when running scripts directly.
- Import specific names: `from backend.classifier import QueryClassifier, STATIC`.

### Naming
- **snake_case** for functions, variables, methods, modules.
- **PascalCase** for classes (`QueryClassifier`, `ResponseFormatter`, `OllamaLLM`).
- **UPPER_SNAKE** for constants (`OLLAMA_BASE_URL`, `RETRIEVER_CONFIG`, `STATIC_ANSWERS`).
- Private methods prefixed with `_` (`_expand_query`, `_bm25_search`, `_clean_answer`).

### Types
- Type hints used sparingly — primarily in `backend/settings.py` dataclasses and return types.
- No mandatory type checking or mypy. Use `Optional[T]` from `typing` when needed.

### Formatting
- 4-space indentation. No formatter (black/ruff) enforced.
- Keep lines under ~100 chars; break long expressions naturally.
- Use docstrings for classes and public methods (triple-quoted, concise).
- Section separators: `# ====` comment blocks for major sections.

### Error Handling
- Catch specific exceptions: `requests.ConnectionError`, `requests.Timeout`, `requests.HTTPError`.
- Return graceful fallback dicts from LLM calls: `{"text": "...", "error": "timeout"}`.
- Use `try/except Exception: pass` for non-critical cache writes.
- Print user-facing errors to stdout with emoji markers (`❌`, `⚠️`, `✅`).

### General Patterns
- Configuration lives in `config.py` — never hardcode paths elsewhere.
- Static answers go in `STATIC_ANSWERS` dict in `classifier.py` — single source of truth.
- Query classification is regex-based with Urdu/typo tolerance — add patterns to existing lists.
- Use `re.DOTALL` flag for multi-line regex (especially for Qwen think tag stripping).
- Streaming via generators (`yield`) — both LLM responses and SSE in the API.

---

## Data Pipeline

1. Place raw PDFs in `data/raw/`
2. Run `uv run knowledge/process_data.py` → outputs to `data/processed/` (chunks.json, qa_pairs.json)
3. Run `uv run retrieval/build_index.py` → outputs to `data/index/` (embeddings.npy, bm25.pkl, documents.json)

---

## Prerequisites

- **Ollama** must be running (`ollama serve`) with models pulled:
  - `ollama pull llama3.2:3b` (default generation model)
  - `ollama pull nomic-embed-text` (embedding model)
- No cloud APIs required — everything runs locally.

---

## Key Conventions

- **Do not** modify `config.py` paths without updating data pipeline scripts.
- **Do not** duplicate `QueryClassifier` — import from `backend/classifier.py`.
- When adding new static answers, add to both `STATIC_ANSWERS` dict and update `classifier.py` intent matching if needed.
- Test results are saved to `test_results/` (gitignored). JSON + Markdown output.
- Windows compatibility: `sys.stdout.reconfigure(encoding="utf-8")` used in scripts that output emoji.
