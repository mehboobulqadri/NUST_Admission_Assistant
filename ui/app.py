"""
NUST Admission Bot — Web Interface (FastAPI)
"""

import sys
import os
import argparse
import time
import re
import json
import platform
import threading
import requests

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from config import INDEX_DIR, PROCESSED_DIR
from retrieval.retriever import Retriever
from llm.ollama_client import OllamaLLM
from llm.prompt_builder import PromptBuilder
from llm.response_formatter import ResponseFormatter
from backend.classifier import QueryClassifier, STATIC
from backend.settings import SettingsManager

# ============================================================
# GLOBAL ENGINE & SETTINGS
# ============================================================
engine = None
settings_manager = SettingsManager()

# Chat statistics tracker
chat_stats = {
    "total_queries": 0,
    "fast_path_hits": 0,
    "llm_hits": 0,
    "static_hits": 0,
    "total_tokens_generated": 0,
    "total_response_time": 0.0,
    "last_response_time": 0.0,
    "last_tokens_per_sec": 0.0,
    "start_time": time.time(),
}


def init_engine(model, num_gpu=None, num_thread=None):
    global engine
    print(f"Initializing Chat Engine with model: {model}...")

    use_distilled = num_gpu == 0
    settings = settings_manager.get_settings()

    engine = {
        "retriever": Retriever(num_gpu=num_gpu, num_thread=num_thread),
        "llm": OllamaLLM(
            model=model,
            temperature=settings.llm.temperature,
            num_ctx=settings.llm.num_ctx,
            num_gpu=num_gpu,
            num_thread=num_thread,
        ),
        "prompt_builder": PromptBuilder(use_distilled=settings.prompt.use_distilled),
        "formatter": ResponseFormatter(),
        "classifier": QueryClassifier(),
    }
    engine["llm"].check_connection()
    print("Chat Engine ready!\n")


# ============================================================
# FASTAPI APP & ROUTES
# ============================================================
app = FastAPI(title="NUST Admission Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: list = []


class ModelRequest(BaseModel):
    model: str


class SettingsUpdateRequest(BaseModel):
    retriever: dict = None
    llm: dict = None
    prompt: dict = None


@app.get("/api/models")
def get_models():
    """Fetch locally downloaded Ollama models."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return {
                "models": [m["name"] for m in models],
                "current": engine["llm"].model,
            }
        return {"models": [engine["llm"].model], "current": engine["llm"].model}
    except Exception as e:
        print(f"Failed to fetch models from Ollama: {e}")
        return {"models": [engine["llm"].model], "current": engine["llm"].model}


@app.post("/api/set_model")
def set_model(req: ModelRequest):
    """Update the LLM model dynamically."""
    if engine and req.model:
        engine["llm"].model = req.model
        return {"status": "success", "model": engine["llm"].model}
    return {"status": "error", "message": "Engine not initialized"}


@app.get("/api/settings")
def get_settings():
    """Get current settings."""
    settings = settings_manager.get_settings()
    return settings.to_dict()


@app.post("/api/settings")
def update_settings(req: SettingsUpdateRequest):
    """Update settings and apply to engine."""
    try:
        updates = {}
        if req.retriever:
            updates["retriever"] = req.retriever
        if req.llm:
            updates["llm"] = req.llm
        if req.prompt:
            updates["prompt"] = req.prompt

        new_settings = settings_manager.update_settings(updates)

        # Apply to engine components
        if req.llm:
            if "temperature" in req.llm:
                engine["llm"].temperature = req.llm["temperature"]
            if "num_ctx" in req.llm:
                engine["llm"].num_ctx = req.llm["num_ctx"]

        if req.prompt:
            if "use_distilled" in req.prompt:
                engine["prompt_builder"].use_distilled = req.prompt["use_distilled"]

        return {"status": "success", "settings": new_settings.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/settings/reset")
def reset_settings():
    """Reset all settings to defaults."""
    new_settings = settings_manager.reset_to_defaults()
    return {"status": "success", "settings": new_settings.to_dict()}


@app.get("/api/analytics")
def get_analytics():
    """Return system and model analytics."""
    import numpy as np

    data = {
        "system": {},
        "model": {},
        "retrieval": {},
        "chat": {},
        "ollama": {},
    }

    # --- System metrics ---
    if HAS_PSUTIL:
        mem = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        disk = psutil.disk_usage("/" if sys.platform != "win32" else "C:\\")

        data["system"] = {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_cores_physical": psutil.cpu_count(logical=False),
            "cpu_cores_logical": psutil.cpu_count(logical=True),
            "cpu_percent": cpu_percent,
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_used_gb": round(mem.used / (1024**3), 2),
            "ram_available_gb": round(mem.available / (1024**3), 2),
            "ram_percent": mem.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_percent": round(disk.used / disk.total * 100, 1),
            "python_version": platform.python_version(),
        }

        # Process-specific memory
        try:
            proc = psutil.Process()
            proc_mem = proc.memory_info()
            data["system"]["process_ram_mb"] = round(proc_mem.rss / (1024**2), 1)
            data["system"]["process_cpu_percent"] = proc.cpu_percent(interval=0.0)
        except Exception:
            pass
    else:
        data["system"] = {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_cores_logical": os.cpu_count(),
            "python_version": platform.python_version(),
            "note": "Install psutil for full system metrics: uv add psutil",
        }

    # --- Model info ---
    if engine:
        llm = engine["llm"]
        data["model"] = {
            "name": llm.model,
            "mode": "CPU"
            if llm.num_gpu == 0
            else "GPU (auto)"
            if llm.num_gpu is None
            else f"GPU ({llm.num_gpu} layers)",
            "temperature": llm.temperature,
            "num_ctx": llm.num_ctx,
            "num_thread": llm.num_thread,
            "cache_entries": len(llm.cache),
            "is_qwen": llm.is_qwen,
            "is_gemma": llm.is_gemma,
        }

    # --- Retrieval info ---
    if engine:
        retriever = engine["retriever"]
        num_qa = len(retriever.qa_indices)
        num_chunks = len(retriever.documents) - num_qa
        emb_dim = retriever.embeddings.shape[1] if retriever.embeddings.ndim > 1 else 0
        emb_mem_mb = round(retriever.embeddings.nbytes / (1024**2), 1)
        data["retrieval"] = {
            "total_documents": len(retriever.documents),
            "chunks": num_chunks,
            "qa_pairs": num_qa,
            "embedding_dim": emb_dim,
            "embedding_memory_mb": emb_mem_mb,
            "embed_cache_size": len(retriever._embed_cache),
            "synonyms_count": len(retriever.synonyms),
            "bm25_weight": retriever.config.get("bm25_weight", 0.45),
            "vector_weight": retriever.config.get("vector_weight", 0.55),
        }

    # --- Chat stats ---
    uptime = time.time() - chat_stats["start_time"]
    avg_time = (
        chat_stats["total_response_time"] / chat_stats["total_queries"]
        if chat_stats["total_queries"] > 0
        else 0
    )
    data["chat"] = {
        **chat_stats,
        "uptime_seconds": round(uptime, 0),
        "avg_response_time": round(avg_time, 2),
    }

    # --- Ollama status ---
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            data["ollama"] = {
                "status": "running",
                "models_available": [m["name"] for m in models],
                "total_models": len(models),
                "total_size_gb": round(
                    sum(m.get("size", 0) for m in models) / (1024**3), 2
                ),
            }
        else:
            data["ollama"] = {"status": "error", "code": resp.status_code}
    except Exception:
        data["ollama"] = {"status": "offline"}

    return data


@app.get("/api/analytics/stream")
async def analytics_stream():
    """SSE endpoint for live system metrics."""

    async def event_generator():
        for _ in range(60):  # Stream for ~60 seconds
            metrics = {}
            if HAS_PSUTIL:
                mem = psutil.virtual_memory()
                metrics = {
                    "cpu_percent": psutil.cpu_percent(interval=0.3),
                    "ram_percent": mem.percent,
                    "ram_used_gb": round(mem.used / (1024**3), 2),
                    "timestamp": time.time(),
                }
                try:
                    proc = psutil.Process()
                    metrics["process_ram_mb"] = round(
                        proc.memory_info().rss / (1024**2), 1
                    )
                except Exception:
                    pass
            yield f"data: {json.dumps(metrics)}\n\n"
            import asyncio

            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def respond_stream(message: str, history: list):
    if not message or not message.strip():
        yield f"data: {json.dumps({'text': 'Please ask me a question about NUST admissions!'})}\n\n"
        return

    message = message.strip()
    start_time = time.time()
    settings = settings_manager.get_settings()

    # --- Static responses ---
    query_type = engine["classifier"].classify(message)

    if query_type.startswith("static:"):
        from backend.classifier import STATIC_ANSWERS

        key = query_type.split(":", 1)[1]
        static_answer = STATIC_ANSWERS.get(key, "I don't have that information.")
        chat_stats["total_queries"] += 1
        chat_stats["static_hits"] += 1
        chat_stats["last_response_time"] = round(time.time() - start_time, 3)
        words = static_answer.split(" ")
        # 2-3 second thinking pause before first word
        time.sleep(2.5)
        collected = []
        for w in words:
            collected.append(w)
            yield f"data: {json.dumps({'text': ' '.join(collected)})}\n\n"
            time.sleep(0.035)  # ~1.5s for 40-word response
        return

    if query_type in STATIC:
        chat_stats["total_queries"] += 1
        chat_stats["static_hits"] += 1
        chat_stats["last_response_time"] = round(time.time() - start_time, 3)
        words = STATIC[query_type].split(" ")
        # Greetings: 1-2s thinking pause; others: 2-3s
        think_delay = 1.5 if query_type == "greeting" else 2.5
        time.sleep(think_delay)
        collected = []
        for w in words:
            collected.append(w)
            yield f"data: {json.dumps({'text': ' '.join(collected)})}\n\n"
            time.sleep(0.04)
        return

    # --- Retrieve with dynamic top_k ---
    retriever = engine["retriever"]
    top_k = settings.retriever.top_k
    results = retriever.retrieve(message, top_k=top_k)
    if not results:
        msg = "I couldn't find relevant information about this. Please visit nust.edu.pk or contact the NUST admission office."
        words = msg.split(" ")
        time.sleep(2.0)
        collected = []
        for w in words:
            collected.append(w)
            yield f"data: {json.dumps({'text': ' '.join(collected)})}\n\n"
            time.sleep(0.04)
        return

    # --- Fast path ---
    if len(results) == 1 and results[0].get("method") in [
        "fast_path",
        "fast_path_keyword",
    ]:
        answer = results[0]["content"]
        elapsed = time.time() - start_time
        chat_stats["total_queries"] += 1
        chat_stats["fast_path_hits"] += 1
        chat_stats["last_response_time"] = round(elapsed, 3)
        # Clean the answer through formatter (strips metadata)
        cleaned = engine["formatter"].format(
            answer_text=answer,
            sources=[],
            method="fast_path",
            response_time=elapsed,
        )
        words = cleaned.split(" ")
        # 3-4 second thinking pause for fast-path (simulate reasoning)
        time.sleep(3.2)
        collected = []
        for w in words:
            collected.append(w)
            yield f"data: {json.dumps({'text': ' '.join(collected)})}\n\n"
            time.sleep(0.055)  # ~3-4s for 60-word response
        return

    # --- Build conversation history ---
    conv_history = None
    if history and settings.prompt.include_history:
        msg_lower = message.lower()
        followup_signals = [
            "what about",
            "how about",
            "and ",
            "also ",
            "what else",
            "tell me more",
            "too",
        ]
        is_followup = any(s in msg_lower for s in followup_signals)
        if is_followup:
            conv_history = []
            for u, b in history[-2:]:
                if u:
                    conv_history.append(("user", u))
                if b:
                    clean = "\n".join(
                        l
                        for l in b.split("\n")
                        if not l.startswith(("Sources:", "Direct", "Response"))
                    ).strip()[:200]
                    conv_history.append(("assistant", clean))

    # --- Build prompt with custom system prompt if provided ---
    injected_facts = engine["classifier"].extract_facts(message)

    # Use custom system prompt if provided
    custom_system_prompt = settings.prompt.system_prompt

    prompt, sys_prompt, sources = engine["prompt_builder"].build(
        query=message,
        retrieved_results=results,
        conversation_history=conv_history,
        injected_facts=injected_facts,
    )

    # Override system prompt if custom one is provided
    if custom_system_prompt:
        sys_prompt = custom_system_prompt

    # --- Stream LLM response ---
    llm = engine["llm"]
    collected = []

    for token in llm.generate_stream(prompt=prompt, system_prompt=sys_prompt):
        collected.append(token)
        full = "".join(collected)

        cleaned = re.sub(r"<think>.*?</think>", "", full, flags=re.DOTALL)
        cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL)
        cleaned = cleaned.replace("</think>", "").strip()
        if cleaned:
            yield f"data: {json.dumps({'text': cleaned})}\n\n"

    # --- Final format with sources ---
    elapsed = time.time() - start_time
    full_response = "".join(collected)
    full_response = re.sub(r"<think>.*?</think>", "", full_response, flags=re.DOTALL)
    full_response = re.sub(r"<think>.*$", "", full_response, flags=re.DOTALL)
    full_response = full_response.replace("</think>", "").strip()

    # Track LLM stats
    token_count = len(full_response.split())
    tokens_per_sec = round(token_count / elapsed, 1) if elapsed > 0 else 0
    chat_stats["total_queries"] += 1
    chat_stats["llm_hits"] += 1
    chat_stats["total_tokens_generated"] += token_count
    chat_stats["total_response_time"] += elapsed
    chat_stats["last_response_time"] = round(elapsed, 3)
    chat_stats["last_tokens_per_sec"] = tokens_per_sec

    formatted = engine["formatter"].format(
        answer_text=full_response,
        sources=sources,
        method="hybrid",
        response_time=elapsed,
    )
    yield f"data: {json.dumps({'text': formatted})}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/api/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        respond_stream(req.message, req.history), media_type="text/event-stream"
    )


# Mount Static UI and Resources
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount(
        "/resources",
        StaticFiles(directory=os.path.join(PROJECT_ROOT, "resources")),
        name="resources",
    )
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    print(f"Warning: Frontend directory not found at {FRONTEND_DIR}")


# ============================================================
# MAIN
# ============================================================
def create_app(
    model="llama3.2:3b", host="0.0.0.0", port=8000, num_gpu=None, num_thread=None
):
    init_engine(model, num_gpu=num_gpu, num_thread=num_thread)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NUST Admission Bot - Web UI")
    parser.add_argument("--model", default="llama3.2:3b", help="Ollama model to use")
    parser.add_argument("--host", default="127.0.0.1", help="Host IP")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    parser.add_argument(
        "--cpu", action="store_true", help="Force CPU-only mode (num_gpu=0)"
    )

    args = parser.parse_args()

    # Initialize with CPU mode if requested (8 threads optimized for CPU)
    num_gpu = 0 if args.cpu else None
    num_thread = 8 if args.cpu else None

    create_app(
        model=args.model,
        host=args.host,
        port=args.port,
        num_gpu=num_gpu,
        num_thread=num_thread,
    )
