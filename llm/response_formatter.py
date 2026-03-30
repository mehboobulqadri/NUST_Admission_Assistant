"""
Response Formatter — FIXED
Handles Qwen think tags (both closed and unclosed)
"""

import re


class ResponseFormatter:

    @staticmethod
    def format(
        answer_text,
        sources,
        method="hybrid",
        response_time=None,
        tokens_per_second=None,
    ):
        cleaned = ResponseFormatter._clean_answer(answer_text)
        # Return only the clean answer — no metadata, no source lines, no timing
        return cleaned


    @staticmethod
    def _clean_answer(text):
        """Clean LLM output — handles Qwen think tags, Fact: leakage, and 1B artifacts."""
        if not text:
            return (
                "I'm sorry, I couldn't generate a response. "
                "Please try rephrasing your question."
            )

        # ============================================
        # FIX: Handle Qwen3 <think> blocks properly
        # ============================================

        # Case 1: Properly closed <think>...</think> — remove it
        text = re.sub(
            r'<think>.*?</think>',
            '',
            text,
            flags=re.DOTALL,
        )

        # Case 2: Unclosed <think> (model hit token limit mid-thinking)
        # Remove everything from <think> to end of string
        text = re.sub(
            r'<think>.*$',
            '',
            text,
            flags=re.DOTALL,
        )

        # Case 3: Stray closing tag
        text = text.replace('</think>', '')

        # ============================================
        # General cleanup
        # ============================================
        text = text.strip()

        if not text:
            return (
                "I'm sorry, I couldn't generate a response. "
                "Please try rephrasing your question."
            )

        # Remove prompt leakage
        leakage_patterns = [
            r'^(Answer|Response|Assistant|Bot):?\s*',
            r'^Based on the (provided |above )?(?:context|information),?\s*',
            r'^According to the (provided |above )?(?:context|information|sources?),?\s*',
        ]
        for pattern in leakage_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # ── 1B model artifact cleanup ───────────────────────────────────────

        # Strip "Fact:" prefix from start of lines (1B leaks this from injected facts)
        text = re.sub(r'(?m)^Fact:\s*', '', text)

        # Fix "Yes, there are no" binary contradiction → "There are no"
        text = re.sub(
            r"^Yes,?\s+there are no",
            "There are no",
            text, flags=re.IGNORECASE
        )

        # Fix "Yes, I don't have this" contradiction → drop the "Yes,"
        text = re.sub(
            r"^Yes,?\s+(I don.?t have|I do not have|I don.?t have this)",
            r"I don't have this information. Visit nust.edu.pk.",
            text, flags=re.IGNORECASE
        )

        # AGGRESSIVE PRUNING:
        # If the model gives a valid answer (e.g. 30+ chars) then appends a refusal,
        # strip the refusal to avoid "Double Response" syndrome.
        refusal_phrases = [
            r"I don't have (?:specific )?information.*$",
            r"I don't have this.*$",
            r"Visit nust.edu.pk.*$"
        ]
        
        # Only prune if there was a substantial answer before the refusal
        lines = text.split('\n')
        if len(lines) > 1:
            first_part = lines[0].strip()
            if len(first_part) > 30 and not any(re.search(p, first_part, re.I) for p in refusal_phrases):
                # Check if subsequent lines contain a refusal
                new_lines = [lines[0]]
                for line in lines[1:]:
                    if any(re.search(p, line, re.I) for p in refusal_phrases):
                        break # Stop including lines
                    new_lines.append(line)
                text = "\n".join(new_lines)

        # Strip "Yes/No:" judge labels
        text = re.sub(r'(?m)^Yes/No:\s*', '', text)
        text = re.sub(r'\bYes/No\b', '', text)

        # Strip "Student: ..." echo lines
        text = re.sub(r'(?m)^Student:\s*.+$', '', text)

        # Collapse multiple blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)

        text = text.strip()

        if text and text[0].islower():
            text = text[0].upper() + text[1:]

        return text.strip()

    @staticmethod
    def _clean_source_name(source):
        source = source.replace(
            "Marcoms-Prospectus-2025-V.5.0-04032025 Compressed",
            "NUST Prospectus 2025",
        )
        source = re.sub(r'\s*\(Table,\s*', ' (Table, ', source)
        if len(source) > 60:
            source = source[:57] + "..."
        return source