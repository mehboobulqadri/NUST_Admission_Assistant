"""
NUST Admission Bot — Web Interface (FastAPI)
"""

import sys
import os
import argparse
import time
import re
import json
import requests

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from retrieval.retriever import Retriever
from llm.ollama_client import OllamaLLM
from llm.prompt_builder import PromptBuilder
from llm.response_formatter import ResponseFormatter
from backend.classifier import QueryClassifier, STATIC

# ============================================================
# GLOBAL ENGINE
# ============================================================
engine = None

def init_engine(model, num_gpu=None, num_thread=None):
    global engine
    print(f"Initializing Chat Engine with model: {model}...")
    
    use_distilled = (num_gpu == 0)
    
    engine = {
        "retriever": Retriever(num_gpu=num_gpu, num_thread=num_thread),
        "llm": OllamaLLM(model=model, temperature=0.3, num_gpu=num_gpu, num_thread=num_thread),
        "prompt_builder": PromptBuilder(use_distilled=use_distilled),
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

@app.get("/api/models")
def get_models():
    """Fetch locally downloaded Ollama models."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return {"models": [m["name"] for m in models], "current": engine["llm"].model}
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

def respond_stream(message: str, history: list):
    if not message or not message.strip():
        yield f"data: {json.dumps({'text': 'Please ask me a question about NUST admissions!'})}\n\n"
        return

    message = message.strip()
    start_time = time.time()

    # --- Static responses ---
    query_type = engine["classifier"].classify(message)
    
    if query_type.startswith("static:"):
        from backend.classifier import STATIC_ANSWERS
        key = query_type.split(":", 1)[1]
        static_answer = STATIC_ANSWERS.get(key, "I don't have that information.")
        words = static_answer.split(" ")
        collected = []
        for w in words:
            collected.append(w)
            yield f"data: {json.dumps({'text': ' '.join(collected)})}\n\n"
            time.sleep(0.01) # Ultra-fast typing for static info
        return

    if query_type in STATIC:
        words = STATIC[query_type].split(" ")
        collected = []
        for w in words:
            collected.append(w)
            yield f"data: {json.dumps({'text': ' '.join(collected)})}\n\n"
            time.sleep(0.04)
        return

    # --- Retrieve ---
    retriever = engine["retriever"]
    top_k = 1 if "1b" in engine["llm"].model.lower() else 3
    results = retriever.retrieve(message, top_k=top_k)
    if not results:
        msg = "I couldn't find relevant information about this. Please visit nust.edu.pk or contact the NUST admission office."
        words = msg.split(" ")
        collected = []
        for w in words:
            collected.append(w)
            yield f"data: {json.dumps({'text': ' '.join(collected)})}\n\n"
            time.sleep(0.04)
        return

    # --- Fast path ---
    if len(results) == 1 and results[0].get("method") in ["fast_path", "fast_path_keyword"]:
        answer = results[0]["content"]
        source = results[0].get("source", "")
        elapsed = time.time() - start_time
        formatted = engine["formatter"].format(
            answer_text=answer,
            sources=[source],
            method=results[0].get("method", "fast_path"),
            response_time=elapsed,
        )
        words = formatted.split(" ")
        collected = []
        for w in words:
            collected.append(w)
            yield f"data: {json.dumps({'text': ' '.join(collected)})}\n\n"
            # Faster typing for fast-path answers
            time.sleep(0.01)
        return

    # --- Build conversation history ---
    conv_history = None
    if history:
        msg_lower = message.lower()
        followup_signals = [
            "what about", "how about", "and ", "also ",
            "what else", "tell me more", "too",
        ]
        is_followup = any(s in msg_lower for s in followup_signals)
        if is_followup:
            conv_history = []
            for u, b in history[-2:]:
                if u:
                    conv_history.append(("user", u))
                if b:
                    clean = "\n".join(
                        l for l in b.split("\n")
                        if not l.startswith(("Sources:", "Direct", "Response"))
                    ).strip()[:200]
                    conv_history.append(("assistant", clean))

    # --- Build prompt ---
    injected_facts = engine["classifier"].extract_facts(message)
    prompt, sys_prompt, sources = engine["prompt_builder"].build(
        query=message,
        retrieved_results=results,
        conversation_history=conv_history,
        injected_facts=injected_facts,
    )

    # --- Stream LLM response ---
    llm = engine["llm"]
    collected = []

    for token in llm.generate_stream(prompt=prompt, system_prompt=sys_prompt):
        collected.append(token)
        full = "".join(collected)

        cleaned = re.sub(r'<think>.*?</think>', '', full, flags=re.DOTALL)
        cleaned = re.sub(r'<think>.*$', '', cleaned, flags=re.DOTALL)
        cleaned = cleaned.replace('</think>', '').strip()
        if cleaned:
            yield f"data: {json.dumps({'text': cleaned})}\n\n"

    # --- Final format with sources ---
    elapsed = time.time() - start_time
    full_response = "".join(collected)
    full_response = re.sub(r'<think>.*?</think>', '', full_response, flags=re.DOTALL)
    full_response = re.sub(r'<think>.*$', '', full_response, flags=re.DOTALL)
    full_response = full_response.replace('</think>', '').strip()
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
    return StreamingResponse(respond_stream(req.message, req.history), media_type="text/event-stream")

# Mount Static UI and Resources
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/resources", StaticFiles(directory=os.path.join(PROJECT_ROOT, "resources")), name="resources")
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    print(f"Warning: Frontend directory not found at {FRONTEND_DIR}")

# ============================================================
# MAIN
# ============================================================
def create_app(model="llama3.2:3b", host="0.0.0.0", port=8000, num_gpu=None, num_thread=None):
    init_engine(model, num_gpu=num_gpu, num_thread=num_thread)
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NUST Admission Bot - Web UI")
    parser.add_argument("--model", default="llama3.2:3b", help="Ollama model to use")
    parser.add_argument("--host", default="127.0.0.1", help="Host IP")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    parser.add_argument("--cpu", action="store_true", help="Force CPU-only mode (num_gpu=0)")
    
    args = parser.parse_args()
    
    # Initialize with CPU mode if requested (8 threads optimized for CPU)
    num_gpu = 0 if args.cpu else None
    num_thread = 8 if args.cpu else None
    
    create_app(model=args.model, host=args.host, port=args.port, num_gpu=num_gpu, num_thread=num_thread)