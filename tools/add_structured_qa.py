import json
import os
import sys

# Ensure paths work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PROJECT_ROOT

new_qas = [
    {
        "question": "What is the fee for Engineering and Computing programs (BSCS, SE, Mechanical, Civil, Electrical, AI, Data Science)?",
        "answer": "The tuition fee for all Engineering and Computing programs at NUST is Rs. 171,350 per semester. Additionally, there is a one-time Admission Processing Fee of Rs. 35,000 (non-refundable), a Security Deposit of Rs. 10,000 (refundable), and Miscellaneous dues of Rs. 2,700 per semester. For 4 years (8 semesters), the total estimated tuition cost is around Rs. 1.4 Million.",
        "category": "Fees"
    },
    {
        "question": "What is the fee for Business Studies, Social Sciences (S3H), Architecture, and LLB? (BBA, ACF, Economics, etc.)",
        "answer": "The tuition fee for Business (BBA, ACF), Social Sciences (Economics, Psychology, Public Admin, Mass Comm), Architecture, and LLB is Rs. 250,380 per semester. LLB students also pay a Rs. 3,000 Bar Council Registration fee. There is a one-time Admission Processing Fee of Rs. 35,000, Security Deposit of Rs. 10,000, and Miscellaneous dues of Rs. 2,700 per semester.",
        "category": "Fees"
    },
    {
        "question": "What is the fee for BS English?",
        "answer": "The tuition fee for BS English (Language and Literature) is Rs. 85,000 per semester. One-time admission and security fees also apply.",
        "category": "Fees"
    },
    {
        "question": "What are the hostel charges and mess fees at NUST?",
        "answer": "Hostel charges per month: Single with attached bath (Rs. 11,000), Double with attached bath (Rs. 10,000), Double with community bath (Rs. 8,000), Triple with community bath (Rs. 6,750). The mess fee (food) is approximately Rs. 15,175 per month.",
        "category": "Hostel"
    },
    {
        "question": "What is the merit or aggregate criteria formula for NUST admission?",
        "answer": "The NUST aggregate merit formula is: 75% NUST Entry Test (NET) score + 15% HSSC / A-Level / Equivalent score + 10% SSC / O-Level / Equivalent score.",
        "category": "Merit"
    }
]

qa_path = os.path.join(PROJECT_ROOT, "data", "processed", "qa_pairs.json")

with open(qa_path, "r", encoding="utf-8") as f:
    data = json.load(f)

for qa in new_qas:
    qa["source"] = "Structured Extraction from Official NUST Prospectus 2025"
    data.append(qa)

with open(qa_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print(f"✅ Added {len(new_qas)} highly structured QAs for exact queries.")
