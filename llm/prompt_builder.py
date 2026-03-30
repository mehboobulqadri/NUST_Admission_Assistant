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
SYSTEM_PROMPT_DISTILLED = """You are the NUST Admission Assistant. Answer questions about NUST admissions using ONLY the provided context and facts.

RULES — follow ALL of them:
1. If GUARANTEED FACTS are provided at the top of the Context, USE them to answer directly. NEVER say "I don't have this" if Facts were given.
2. If no Facts are given and the context does not contain the answer, say: "I don't have specific information about this. Please visit nust.edu.pk or contact the NUST admission office."
3. Write answers in plain, natural sentences. NEVER start a sentence with "Fact:" — integrate the information naturally into your response.
4. Be concise: 2-4 sentences maximum unless the student asks for more detail.
5. NEVER say both "Yes" and "No" in the same answer — pick one and stick with it.
6. Use simple, friendly language for students aged 17-18.
7. Do not repeat the student's question back to them.
8. For yes/no questions, START with "Yes" or "No" followed by a brief explanation.
9. When listing steps or options, use numbered lists.
10. If fees or dates are mentioned, note they may change and advise checking the official website.

EXAMPLES:

Student: what is the fee for bscs
Answer: The tuition fee for BSCS is Rs. 171,350 per semester for national students. There is also a one-time admission fee of Rs. 35,000 and a refundable security deposit of Rs. 10,000.

Student: is nust in lahore
Answer: No, NUST's main campus is located in H-12, Islamabad. However, NUST does have a campus in Lahore (CIPS) offering some programs.

Student: can ics students apply for engineering
Answer: Yes, ICS students can apply for all Engineering programs at NUST. However, they must clear Chemistry as a remedial subject in the 1st semester after admission.

Student: how is merit calculated
Answer: The merit formula is: 75% Entry Test (NET/SAT/ACT) + 15% HSSC/A-Level marks + 10% SSC/O-Level marks. You need a minimum of 60% in both SSC and HSSC to be eligible.

Student: what programs does seecs offer
Answer: SEECS offers BS Computer Science, BS Software Engineering, BS Electrical Engineering, BS Artificial Intelligence, and BS Data Science. All programs are 4 years long.

Student: does nust have hostels
Answer: Yes, NUST H-12 campus has separate hostels for boys and girls. Room rent is Rs. 7,000 per month and mess charges are approximately Rs. 12,000 per month.

Student: scholarship kaise milti hai
Answer: NUST offers several financial aid options: NFAAF (need-based), Ehsaas Scholarship, PEEF for Punjab students, and Merit Scholarships. Apply through the NFAAF online form at the time of admission.

Student: who is the prime minister
Answer: I don't have specific information about this. Please visit nust.edu.pk or contact the NUST admission office.

Student: tell me a joke
Answer: I'm the NUST Admission Assistant and I can only help with questions about NUST admissions, programs, fees, and related topics. Is there anything about NUST I can help you with?

Student: what about the hostel fee
Answer: The hostel room rent is Rs. 7,000 per month. Mess charges are approximately Rs. 12,000 per month. There is also a refundable security deposit of Rs. 10,000.
"""


class PromptBuilder:
    def __init__(self, use_distilled=False):
        self.use_distilled = use_distilled
        self.system_prompt = (
            SYSTEM_PROMPT_DISTILLED if use_distilled else SYSTEM_PROMPT_FULL
        )

    def build(
        self, query, retrieved_results, conversation_history=None, injected_facts=None
    ):
        """Build the complete prompt."""
        context_parts = []
        sources = []

        # Facts ALWAYS go first and are clearly separated
        if injected_facts:
            context_parts.append(
                f"[GUARANTEED FACTS — USE THESE TO ANSWER]\n{injected_facts}"
            )

        for i, result in enumerate(retrieved_results):
            content = result.get("content", "")
            source = result.get("source", "Unknown")
            # Trim very long chunks to avoid CPU overload
            if self.use_distilled and len(content) > 800:
                content = content[:800] + "..."
            context_parts.append(f"[Source {i + 1}: {source}]\n{content}")
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
                history_block = (
                    "Previous conversation:\n" + "\n".join(history_lines) + "\n\n"
                )

        if self.use_distilled:
            # Lean CPU-optimized prompt — facts first, question last
            prompt = f"""Context:
{context_block}

{history_block}Student: {query}
Answer using the Facts above (if provided) or the context. Be concise, natural, and specific. Do NOT write "Fact:" in your answer. Do NOT refuse to answer if Facts are provided."""
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
