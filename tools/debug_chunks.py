"""
Debug tool — see what chunks the LLM actually receives.

Run:
    python debug_chunks.py
    
    To save to file:
    python debug_chunks.py --save
"""

import sys
import os
import json
import argparse

# Fix Windows Unicode issue
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, ".")

# Temporarily suppress emoji prints from retriever
import io

class SafePrinter:
    """Capture retriever init prints without crashing on Windows."""
    def __init__(self):
        self.original = sys.stdout
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass

from retrieval.retriever import Retriever

retriever = Retriever()

queries = [
    "What is the fee for BSCS?",
    "What is the fee for BBA?",
    "What is the merit criteria?",
    "How do I apply to NUST?",
    "Tell me about hostel facilities",
    "What programs does SEECS offer?",
    "NET test dates and pattern",
    "Scholarship opportunities at NUST",
    "What is the aggregate formula?",
    "Eligibility for engineering programs",
]

output_lines = []

for query in queries:
    output_lines.append("=" * 70)
    output_lines.append(f"QUERY: {query}")
    output_lines.append("=" * 70)

    results = retriever.retrieve(query, top_k=3)

    if not results:
        output_lines.append("  NO RESULTS FOUND")
        output_lines.append("")
        continue

    for i, r in enumerate(results):
        output_lines.append(f"\n--- Result {i+1} [{r['method']}] [{r['category']}] ---")
        output_lines.append(f"Source: {r['source']}")
        output_lines.append(f"Score:  {r['score']}")
        output_lines.append(f"Type:   {r.get('type', 'chunk')}")
        output_lines.append(f"Content ({len(r['content'])} chars):")
        output_lines.append("-" * 40)
        output_lines.append(r["content"])
        output_lines.append("-" * 40)

    output_lines.append("\n")

# Print to console
full_output = "\n".join(output_lines)

parser = argparse.ArgumentParser()
parser.add_argument("--save", action="store_true", help="Save to file")
args = parser.parse_args()

if args.save:
    with open("debug_output.txt", "w", encoding="utf-8") as f:
        f.write(full_output)
    print(f"Saved to debug_output.txt ({len(output_lines)} lines)")
else:
    print(full_output)