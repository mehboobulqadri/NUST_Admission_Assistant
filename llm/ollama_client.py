"""
Ollama LLM Client
=================
Supports multiple model families: Qwen, Gemma, Mistral, Phi, LLaMA, etc.
Model family is auto-detected from the model name.
"""

import requests
import json
import time


class OllamaLLM:
    """
    Thin wrapper around Ollama /api/generate.

    Model family detection:
        - qwen    → inject /no_think instruction (Qwen3 reasoning models)
        - gemma   → standard generation
        - mistral → standard generation
        - phi     → standard generation
        - llama   → standard generation
    """

    def __init__(
        self,
        model="llama3.2:3b",
        base_url="http://localhost:11434",
        temperature=0.3,
        num_ctx=1024,
        num_gpu=None,
        num_thread=8,
    ):
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.num_gpu = num_gpu
        self.num_thread = num_thread
        self.session = requests.Session()
        self.cache = {}  # In-memory response cache

        # Model family detection
        m = model.lower()
        self.is_qwen    = "qwen"    in m
        self.is_gemma   = "gemma"   in m
        self.is_mistral = "mistral" in m
        self.is_phi     = "phi"     in m

    def _get_cache_key(self, prompt, system_prompt):
        import hashlib
        combined = f"{system_prompt}|||{prompt}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _patch_system(self, system_prompt):
        """Inject model-specific instructions if needed."""
        if self.is_qwen and system_prompt:
            return (
                system_prompt
                + "\n\nIMPORTANT: Respond directly. Do NOT use <think> tags."
            )
        return system_prompt

    def check_connection(self):
        """Verify Ollama is running and model is available."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags", timeout=5
            )
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]

            found = any(
                self.model in name or name.startswith(self.model)
                for name in model_names
            )

            if not found:
                print(f"❌ Model '{self.model}' not found.")
                print(f"   Available: {model_names}")
                print(f"   Run: ollama pull {self.model}")
                return False

            family = (
                "Qwen"    if self.is_qwen    else
                "Gemma"   if self.is_gemma   else
                "Mistral" if self.is_mistral else
                "Phi"     if self.is_phi     else
                "LLaMA/other"
            )
            print(f"✅ LLM ready: {self.model}  [{family}]")
            if self.num_gpu == 0:
                print("   ⚠️ Forced CPU Mode (num_gpu=0)")
            return True

        except requests.ConnectionError:
            print("❌ Cannot connect to Ollama. Run: ollama serve")
            return False

    def generate(self, prompt, system_prompt=""):
        """Generate a response (non-streaming)."""
        key = self._get_cache_key(prompt, system_prompt)
        if key in self.cache:
            return self.cache[key]

        keep_tokens = 64 if self.num_gpu != 0 else 24
        options = {
            "temperature": self.temperature,
            "num_ctx": self.num_ctx,
            "num_predict": 512,
            "num_keep": keep_tokens,
            "stop": ["Student:", "Assistant:", "\nStudent:", "I don't have this.", "Visit nust.edu.pk."],
        }
        if self.num_gpu is not None:
            options["num_gpu"] = self.num_gpu
        if self.num_thread is not None:
            options["num_thread"] = self.num_thread

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }

        sys = self._patch_system(system_prompt)
        if sys:
            payload["system"] = sys

        try:
            start = time.time()
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            elapsed = time.time() - start

            res = {
                "text": result.get("response", "").strip(),
                "done": result.get("done", False),
                "total_duration_ms": result.get("total_duration", 0) / 1_000_000,
                "tokens_generated": result.get("eval_count", 0),
                "tokens_per_second": (
                    result.get("eval_count", 0)
                    / (result.get("eval_duration", 1) / 1_000_000_000)
                    if result.get("eval_duration", 0) > 0
                    else 0
                ),
                "wall_time": round(elapsed, 2),
            }
            self.cache[key] = res
            return res

        except requests.Timeout:
            return {
                "text": "I'm sorry, the response took too long. Please try a shorter question.",
                "done": False,
                "error": "timeout",
            }
        except Exception as e:
            return {
                "text": f"An error occurred: {str(e)}",
                "done": False,
                "error": str(e),
            }

    def generate_stream(self, prompt, system_prompt=""):
        """Generate with streaming — yields tokens as they arrive."""
        key = self._get_cache_key(prompt, system_prompt)
        if key in self.cache:
            yield self.cache[key]["text"]
            return

        # CPU optimization: decrease context and predict limit if on CPU
        keep_tokens = 64 if self.num_gpu != 0 else 24
        ctx_limit = 1024 if self.num_gpu == 0 else self.num_ctx
        predict_limit = 384 if self.num_gpu == 0 else 512

        options = {
            "temperature": self.temperature,
            "num_ctx": ctx_limit,
            "num_predict": predict_limit,
            "num_keep": keep_tokens,
            "stop": ["Student:", "Assistant:", "\nStudent:", "I don't have this.", "Visit nust.edu.pk."],
        }
        if self.num_gpu is not None:
            options["num_gpu"] = self.num_gpu
        if self.num_thread is not None:
            options["num_thread"] = self.num_thread

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": options,
        }

        sys = self._patch_system(system_prompt)
        if sys:
            payload["system"] = sys

        full_text = []
        try:
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=120,
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    if token:
                        full_text.append(token)
                        yield token
                    if chunk.get("done", False):
                        break
            
            # Store in cache
            self.cache[key] = {"text": "".join(full_text)}

        except Exception as e:
            yield f"\n[Error: {str(e)}]"