"""
Prompt Builder — Optimized for Llama 1B CPU inference
Stronger guardrails to prevent Yes/No contradictions,
Fact: leakage, and "I don't have this" when facts ARE provided.
"""


# Original, high-quality prompt for GPU/large models
SYSTEM_PROMPT_FULL = """You are the NUST Admission Assistant, a helpful and accurate chatbot that answers questions about the National University of Sciences and Technology (NUST), Islamabad.

STRICT RULES:
1. ONLY use the information provided in the context below. Do NOT invent or guess any information.
2. If the context does not contain enough information, say: "I don't have specific information about this. Please visit nust.edu.pk or contact the NUST admission office for the latest details."
3. Keep answers concise: 2 to 4 sentences unless the user asks for detail.
4. Be friendly and professional. Use simple language a 17-18 year old student would understand.
5. When mentioning fees or dates, note they may change and advise checking the official website.
6. Answer ONLY the current question. Do NOT add unrelated information.
7. For yes/no questions, START your answer with "Yes" or "No" followed by a brief explanation.
8. When listing steps or options, use numbered lists for clarity."""

# Compressed prompt for CPU / small models (1B, 3B)
# Key improvements over previous version:
#   - Facts at top with explicit USE instruction
#   - Explicit ban on "Fact:" prefix leak
#   - Ban on contradictory Yes/No
#   - "If FACTS are given, NEVER say I don't have this"
SYSTEM_PROMPT_DISTILLED = """You are the NUST Admission Assistant. Answer questions about NUST admissions.

RULES — follow ALL of them:
1. If GUARANTEED FACTS are provided at the top of the Context, USE them to answer. NEVER say "I don't have this" if Facts were given.
2. If no Facts and the context does not contain the answer, say ONLY: "I don't have this. Visit nust.edu.pk."
3. Write answers in plain, natural sentences. NEVER start a sentence with "Fact:" — integrate the information naturally.
4. Be concise: maximum 3-4 sentences. No rambling.
5. NEVER say both "Yes" and "No" in the same answer — pick one and explain.
6. Simple, friendly language for students aged 17-18.
7. Do not repeat the student's question back to them.

EXAMPLES:
Student: what is the fee for bscs
Answer: The tuition fee for BSCS is Rs. 171,350 per semester for national students.

Student: is nust in lahore
Answer: No, NUST's main campus is located in H-12, Islamabad.

Student: who is the prime minister
Answer: I don't have this. Visit nust.edu.pk.
"""


class PromptBuilder:

    def __init__(self, use_distilled=False):
        self.use_distilled = use_distilled
        self.system_prompt = SYSTEM_PROMPT_DISTILLED if use_distilled else SYSTEM_PROMPT_FULL

    def build(self, query, retrieved_results, conversation_history=None, injected_facts=None):
        """Build the complete prompt."""
        context_parts = []
        sources = []

        # Facts ALWAYS go first and are clearly separated
        if injected_facts:
            context_parts.append(f"[GUARANTEED FACTS — USE THESE TO ANSWER]\n{injected_facts}")

        for i, result in enumerate(retrieved_results):
            content = result.get("content", "")
            source = result.get("source", "Unknown")
            # Trim very long chunks to avoid CPU overload
            if self.use_distilled and len(content) > 600:
                content = content[:600] + "..."
            context_parts.append(f"[Source {i+1}: {source}]\n{content}")
            if source not in sources:
                sources.append(source)

        context_block = "\n\n".join(context_parts)

        history_block = ""
        if conversation_history and len(conversation_history) > 0:
            history_lines = []
            recent = conversation_history[-4:]  # last 2 turns
            for role, message in recent:
                if role == "user":
                    history_lines.append(f"Student: {message}")
                elif role == "assistant":
                    short = message[:120] + "..." if len(message) > 120 else message
                    history_lines.append(f"Assistant: {short}")

            if history_lines:
                history_block = "Previous conversation:\n" + "\n".join(history_lines) + "\n\n"

        if self.use_distilled:
            # Lean CPU-optimized prompt — facts first, question last
            prompt = f"""Context:
{context_block}

{history_block}Student: {query}
Answer using the Facts above (if provided) or the context. Be concise and natural. Do NOT write "Fact:" in your answer."""
        else:
            # Original high-fidelity GPU prompt
            prompt = f"""Here is the relevant information from NUST official sources:

---
{context_block}
---

{history_block}Student's question: {query}

Answer the student's question using ONLY the information above. Be concise and helpful."""

        return prompt, self.system_prompt, sources

    def build_fast_path_prompt(self, query, qa_answer, source):
        """For Q&A fast path — optional LLM rephrasing."""
        prompt = f"""Here is the verified answer:

---
{qa_answer}
---

Student's question: {query}

Rephrase this in a friendly, natural way. Keep it to 2-3 sentences. Do not add any new information."""

        return prompt, self.system_prompt, [source]