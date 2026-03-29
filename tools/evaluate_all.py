import subprocess
import json
import os
import glob
import time

models = ["gemma3:4b", "phi4-mini:latest", "llama3.2:3b", "qwen3:4b"]

print("Starting Benchmark Evaluation across all local models...")

for model in models:
    print(f"\n>>>> Evaluating MODEL: {model} (Sample Size: 3/Category) <<<<")
    start_t = time.time()
    subprocess.run(["uv", "run", "python", "tools/test_suite.py", "--model", model, "--sample", "3"])
    print(f"Finished {model} in {time.time() - start_t:.1f}s.")

print("\nAll models evaluated. Comparing results in test_results folder...")
