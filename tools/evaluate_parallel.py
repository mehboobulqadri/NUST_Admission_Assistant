import subprocess
import time

# We are testing Llama 3.2 and Gemma 3 side-by-side. 
# Note: Ollama handles parallel requests automatically, but running *two different models* 
# at the exact same time might cause Ollama to constantly swap them in and out of GPU memory.
# If speeds are horrible, run them sequentially instead!

print("🚀 Launching Parallel Evaluation for Llama 3.2 and Gemma 3...")
start_time = time.time()

# We'll run the full 230+ question suite.
p_llama = subprocess.Popen(["uv", "run", "python", "tools/test_suite.py", "--model", "llama3.2:3b"])
p_gemma = subprocess.Popen(["uv", "run", "python", "tools/test_suite.py", "--model", "gemma3:4b"])

print("⏳ Waiting for both test suites to finish...")

p_llama.wait()
p_gemma.wait()

print(f"✅ Parallel evaluation complete in {time.time() - start_time:.1f} seconds!")
print("Check the test_results/ folder. Pass me the generated JSON or MD files and I will analyze them for accuracy, hallucinations, and quality!")
