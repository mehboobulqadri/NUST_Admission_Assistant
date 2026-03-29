# tools/extract_faqs.py

import json
import os
import re
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# -------------------------------
# 🔹 EXTRACT Q&A (ROBUST VERSION)
# -------------------------------
def extract_qa_from_text(text, source="NUST FAQ"):
    pairs = []

    text = text.replace("\r", "").strip()

    # ---------- METHOD 1: Q: A: ----------
    parts = re.split(r'\n\s*Q\s*[:\.]\s*', text, flags=re.IGNORECASE)

    for part in parts[1:]:
        qa_split = re.split(r'\n\s*A\s*[:\.]\s*', part, maxsplit=1, flags=re.IGNORECASE)

        if len(qa_split) == 2:
            q = qa_split[0].strip()
            a = qa_split[1].strip()

            # remove next Q bleeding
            next_q = re.search(r'\n\s*Q\s*[:\.]\s*', a, flags=re.IGNORECASE)
            if next_q:
                a = a[:next_q.start()].strip()

            if q and a and len(a) > 20:
                pairs.append({"question": q, "answer": a, "source": source})

    # ---------- METHOD 2: NUMBERED ----------
    blocks = re.split(r'\n\s*\d+\.\s+', text)

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        q = lines[0].strip()
        a = " ".join(lines[1:]).strip()

        if "?" in q and len(a) > 30:
            pairs.append({"question": q, "answer": a, "source": source})

    # ---------- METHOD 3: QUESTION MARK ----------
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if line.endswith("?") and len(line) > 10:
            question = line
            answer_lines = []

            i += 1
            while i < len(lines) and not lines[i].strip().endswith("?"):
                answer_lines.append(lines[i].strip())
                i += 1

            answer = " ".join(answer_lines).strip()

            if len(answer) > 30:
                pairs.append({
                    "question": question,
                    "answer": answer,
                    "source": source
                })
        else:
            i += 1

    return pairs


# -------------------------------
# 🔹 MAIN SCRIPT
# -------------------------------
def main():
    raw_dir = "data/raw"
    qa_path = "data/processed/qa_pairs.json"

    # Load existing QA pairs
    with open(qa_path, "r", encoding="utf-8") as f:
        existing_qa = json.load(f)

    existing_questions = {
        qa["question"].lower().strip() for qa in existing_qa
    }

    print(f"Existing QA pairs: {len(existing_qa)}")

    new_pairs = []

    # 🔥 FIXED FAQ KEYWORDS
    FAQ_KEYWORDS = [
        "faq",
        "faqs",
        "frequently_asked_questions",
        "frequently asked questions",
        "question"
    ]

    # Process files
    for filename in sorted(os.listdir(raw_dir)):

        if not filename.endswith(".txt"):
            continue

        name = filename.lower()

        print(f"\nChecking file: {filename}")

        # 🔥 FIXED FILE DETECTION
        if not any(keyword in name for keyword in FAQ_KEYWORDS):
            print("  ❌ Skipped (not FAQ)")
            continue

        print("  ✅ Processing as FAQ")

        filepath = os.path.join(raw_dir, filename)

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract source
        source = filename.replace(".txt", "").replace("_", " ").title()

        for line in content.split("\n"):
            if line.startswith("SOURCE_TITLE:"):
                source = line.replace("SOURCE_TITLE:", "").strip()
                break

        pairs = extract_qa_from_text(content, source)
        print(f"  Found {len(pairs)} Q&A pairs")

        for pair in pairs:
            question_clean = pair["question"].lower().strip()

            if question_clean in existing_questions:
                print(f"  ⚠️ SKIP duplicate: {pair['question'][:60]}")
                continue

            # ---------- CATEGORY ----------
            q_lower = question_clean

            if any(w in q_lower for w in ["fee", "cost", "tuition", "charges"]):
                category = "fees"
            elif any(w in q_lower for w in ["merit", "aggregate", "cutoff", "marks"]):
                category = "merit"
            elif any(w in q_lower for w in ["eligible", "eligibility", "requirement", "qualification"]):
                category = "eligibility"
            elif any(w in q_lower for w in ["net", "entry test", "test pattern"]):
                category = "net_test"
            elif any(w in q_lower for w in ["apply", "application", "admission", "register"]):
                category = "admission_process"
            elif any(w in q_lower for w in ["hostel", "accommodation", "room"]):
                category = "hostel"
            elif any(w in q_lower for w in ["scholarship", "financial", "waiver"]):
                category = "scholarships"
            elif any(w in q_lower for w in ["program", "degree", "course", "school"]):
                category = "programs"
            else:
                category = "general"

            # ---------- KEYWORDS ----------
            words = re.findall(r'[a-zA-Z]{3,}', q_lower)

            stopwords = {
                "the", "is", "are", "was", "what", "how", "can", "for",
                "and", "but", "with", "from", "this", "that", "have",
                "has", "will", "you", "your", "nust"
            }

            keywords = [w for w in words if w not in stopwords][:8]

            # ---------- CLEAN ANSWER ----------
            answer = re.sub(r'\s+', ' ', pair["answer"]).strip()

            qa_entry = {
                "id": f"qa_faq_{len(existing_qa) + len(new_pairs):04d}",
                "type": "qa",
                "question": pair["question"],
                "answer": answer,
                "content": f"{pair['question']} {answer}",
                "keywords": keywords,
                "source": pair["source"],
                "category": category,
            }

            new_pairs.append(qa_entry)
            existing_questions.add(question_clean)

            print(f"  ✅ ADD: {pair['question'][:60]}")

    # Save results
    if new_pairs:
        existing_qa.extend(new_pairs)

        with open(qa_path, "w", encoding="utf-8") as f:
            json.dump(existing_qa, f, indent=2, ensure_ascii=False)

        print(f"\n🎉 Added {len(new_pairs)} new QA pairs")
        print(f"📊 Total QA pairs: {len(existing_qa)}")
        print(f"\n➡️ Now run: python retrieval/build_index.py")
    else:
        print("\n⚠️ No new QA pairs found.")


if __name__ == "__main__":
    main()