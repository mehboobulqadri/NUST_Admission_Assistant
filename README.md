# NUST Admission Assistant

A robust, entirely local Retrieval-Augmented Generation (RAG) chatbot designed to answer undergraduate admission inquiries for the National University of Sciences and Technology (NUST), Pakistan.

## Key Architecture

- **100% Local Inference**: Operates securely via Ollama. No user data is transmitted externally.
- **Hybrid Fast-Path (100% Accuracy)**: Critical NUST policies (Quota, ICS eligibility, Fees) are hardcoded for 100% reliability, bypassing the LLM for common queries.
- **CPU Optimized (Llama 3.2 3B)**: Fine-tuned context windows (`num_ctx: 1024`) and retrieval weights ensure 3B model runs efficiently on standard laptop CPUs.
- **Real-time Streaming**: Provides immediate feedback via token-by-token streaming, significantly reducing perceived latency.
- **High-Precision Retrieval**: Utilizes a hybrid BM25 and vector index to accurately locate exact clauses and tables from the prospectus.
- **Adversarial Guardrails**: Hardcoded heuristics intercept jailbreaks, off-topic prompts, and out-of-scope (e.g., postgraduate) inquiries instantly.

## Prerequisites

1. **Python 3.10+**
2. **uv**: A lightning-fast Python package and environment manager.
   - *Installation:* Follow the official [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/) or run:
     - **macOS/Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
     - **Windows:** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
3. **Ollama**: Required for running the local inference and embedding models.
   - *Installation:* Download and install from [ollama.com](https://ollama.com/download). Ensure it is running as a background service (`ollama serve`).

## Installation

1. Clone this repository to your local machine:
   ```bash
   git clone https://github.com/mehboobulqadri/NUST_Admission_Assistant.git
   cd NUST_Admission_Assistant
   ```

2. Ensure Ollama is running, then pull your preferred generation model and the required embedding model:
   ```bash
   ollama pull llama3.2:3b
   ollama pull nomic-embed-text
   ```

3. Manage dependencies using `uv` (it will automatically use the `.venv` directory):
   ```bash
   uv sync
   ```
   *(If `uv sync` is not configured, running the scripts below with `uv run` will still utilize or create the necessary environment).*

## Usage

### 1. Rebuilding the Knowledge Base
If you update the source documents in `data/raw/` (e.g., adding a new prospectus PDF or updated FAQs), you must rebuild the indices:

```bash
uv run knowledge/process_data.py
uv run retrieval/build_index.py
```

### 2. Running the Next-Gen Chatbot UI
Launch the beautifully redesigned FastAPI server which natively hooks into your downloaded Ollama models via streaming Server-Sent Events (SSE).

```bash
uv run ui/app.py 
```
*After running, open your web browser and navigate directly to `http://localhost:7860/`.*
*The top right header interface features a dynamic dropdown. Simply switch the dropdown to hotkey any local LLM to handle your admissions inquiries.*

### 3. Executing the Test Suite
An asynchronous test suite of 230+ edge cases and queries is included to benchmark model accuracy and retrieval speed. 
You can run it across all your cached models using the bundled evaluation script:

```bash
# Evaluates a 3-question sample per category across all local models
uv run python tools/evaluate_all.py

# Or run the full 230-Q suite manually on a specific model:
uv run python tools/test_suite.py --model llama3.2:3b
```

## Project Structure

- `backend/`: Core classification heuristics and routing logic.
- `config.py`: Centralized cross-platform path resolution.
- `data/raw/`: Official PDFs and raw contextual documents.
- `data/processed/`: Parsed QA pairs and scraped context.
- `data/index/`: Generated FAISS vector indices and BM25 pickles.
- `knowledge/`: Document chunking and data processing pipelines.
- `llm/`: Prompts, inference integration, and client wrappers for Ollama.
- `retrieval/`: Heavy-lifting BM25 and Vector search implementation.
- `tools/`: Administrator commands, test suites, and data structure scripts.
- `ui/`: User interfaces and presentation layers.
