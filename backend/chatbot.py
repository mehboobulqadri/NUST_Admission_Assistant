"""
NUST Admission Chatbot — Core Backend — FIXED
================================================
Fixes:
  - Greeting/off-topic detection
  - Conversation history no longer pollutes unrelated queries
  - Query classification before retrieval
"""

import sys
import os
import re
import time

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from retrieval.retriever import Retriever
from llm.ollama_client import OllamaLLM
from llm.prompt_builder import PromptBuilder
from llm.response_formatter import ResponseFormatter
from backend.classifier import QueryClassifier, STATIC



# ============================================================
# MAIN CHATBOT CLASS
# ============================================================
class NUSTChatbot:
    """
    Main chatbot class — orchestrates everything.
    
    Fixed Pipeline:
        User message
            → Classify (greeting/identity/query)
            → If non-query → static response (instant)
            → If query → Retrieve → Build prompt → LLM → Format
    """

    def __init__(
        self,
        model="qwen3:4b",
        temperature=0.3,
        use_fast_path=True,
        rewrite_fast_path=False,
    ):
        print("=" * 50)
        print("🤖 Initializing NUST Admission Chatbot")
        print("=" * 50)

        self.retriever = Retriever()
        self.llm = OllamaLLM(
            model=model, temperature=temperature
        )
        self.prompt_builder = PromptBuilder()
        self.formatter = ResponseFormatter()
        self.classifier = QueryClassifier()

        self.use_fast_path = use_fast_path
        self.rewrite_fast_path = rewrite_fast_path

        # Conversation history
        self.conversation_history = []

        if not self.llm.check_connection():
            print(f"\n⚠️  LLM not available. Pull it with:")
            print(f"   ollama pull {model}")

        print("✅ Chatbot ready!\n")

    def chat(self, user_message):
        """Process a user message and return a formatted response (Non-streaming)."""
        # We can just collect tokens from the stream for simplicity
        full_response = ""
        for token in self.chat_stream(user_message):
            if isinstance(token, str):
                full_response += token
            else:
                # If it's the final formatted object (last yield)
                return token
        return full_response

    def chat_stream(self, user_message):
        """
        Process a user message and yield tokens as they arrive.
        Final yield is the fully formatted response object.
        """
        if not user_message or not user_message.strip():
            yield "Please ask me a question about NUST admissions!"
            return

        user_message = user_message.strip()
        start_time = time.time()

        # Step 0: Classify
        query_type = self.classifier.classify(user_message)

        if query_type in STATIC:
            response = STATIC[query_type]
            self.conversation_history.append(("user", user_message))
            self.conversation_history.append(("assistant", response))
            yield response
            return

        # Step 1: Retrieve
        # 3B Speed Optimization: Use top_k=2
        results = self.retriever.retrieve(user_message, top_k=2)

        if not results:
            no_result_msg = (
                "I couldn't find relevant information about this topic. "
                "Please visit nust.edu.pk or contact the NUST admission office."
            )
            yield self.formatter.format(
                no_result_msg,
                sources=[],
                response_time=time.time() - start_time,
            )
            return

        # Step 2: Fast Path
        if (
            self.use_fast_path
            and len(results) == 1
            and results[0].get("method") in ["fast_path", "fast_path_keyword"]
        ):
            yield from self._handle_fast_path_stream(
                user_message, results[0], start_time
            )
            return

        # Step 3: Prompt Building
        relevant_history = self._get_relevant_history(user_message)
        prompt, system_prompt, sources = self.prompt_builder.build(
            query=user_message,
            retrieved_results=results,
            conversation_history=relevant_history,
        )

        # Step 4: Stream from LLM
        full_text = []
        for token in self.llm.generate_stream(prompt, system_prompt):
            full_text.append(token)
            yield token

        final_text = "".join(full_text)

        # Step 5: Format Final Response (for metadata)
        formatted = self.formatter.format(
            answer_text=final_text,
            sources=sources,
            method="hybrid",
            response_time=time.time() - start_time,
        )

        # Step 6: Update History
        self.conversation_history.append(("user", user_message))
        self.conversation_history.append(("assistant", final_text))
        if len(self.conversation_history) > 6:
            self.conversation_history = self.conversation_history[-6:]

        yield formatted

    def _get_relevant_history(self, current_query):
        """
        FIX: Only include conversation history if the current query
        seems related to the previous topic.
        
        This prevents "hello" from getting hostel context injected.
        """
        if not self.conversation_history:
            return None

        # Get the last user message from history
        last_user_msg = ""
        for role, msg in reversed(self.conversation_history):
            if role == "user":
                last_user_msg = msg.lower()
                break

        current_lower = current_query.lower()

        # Check for topic continuity signals
        continuity_signals = [
            # Pronouns suggesting follow-up
            current_lower.startswith("what about"),
            current_lower.startswith("how about"),
            current_lower.startswith("and "),
            current_lower.startswith("also "),
            current_lower.startswith("what else"),
            current_lower.startswith("tell me more"),
            current_lower.startswith("more about"),
            # Referential words
            "it" in current_lower.split(),
            "that" in current_lower.split(),
            "this" in current_lower.split(),
            "its" in current_lower.split(),
            "their" in current_lower.split(),
            "there" in current_lower.split(),
            # Short follow-ups
            len(current_lower.split()) <= 4 and "?" in current_query,
            # The word "too" or "also" suggests continuation
            "too" in current_lower.split(),
            "also" in current_lower.split(),
        ]

        # Check for shared keywords between current and last query
        current_words = set(current_lower.split())
        last_words = set(last_user_msg.split())
        shared = current_words & last_words
        # Remove common words from shared set
        common_words = {
            "the", "is", "are", "what", "how", "can", "i",
            "a", "an", "to", "for", "of", "in", "at", "do",
            "nust", "about",
        }
        meaningful_shared = shared - common_words
        has_shared_topic = len(meaningful_shared) > 0

        if any(continuity_signals) or has_shared_topic:
            return self.conversation_history
        else:
            # New topic — don't inject old context
            return None

    def _handle_fast_path_stream(self, query, qa_result, start_time):
        """Handle Q&A fast path responses in a streaming manner."""
        answer = qa_result["content"]
        source = qa_result.get("source", "")

        if self.rewrite_fast_path:
            prompt, sys_prompt, sources = (
                self.prompt_builder.build_fast_path_prompt(
                    query, answer, source
                )
            )
            full_text = []
            for token in self.llm.generate_stream(prompt, sys_prompt):
                full_text.append(token)
                yield token
            final_text = "".join(full_text)
        else:
            final_text = answer
            yield final_text

        response = self.formatter.format(
            answer_text=final_text,
            sources=[source] if source else [],
            method="fast_path",
            response_time=time.time() - start_time,
        )

        self.conversation_history.append(("user", query))
        self.conversation_history.append(("assistant", final_text))
        return response

    def reset_conversation(self):
        """Clear conversation history."""
        self.conversation_history = []
        print("🔄 Conversation history cleared.")

    def get_stats(self):
        """Return chatbot statistics."""
        return {
            "model": self.llm.model,
            "total_documents": len(self.retriever.documents),
            "qa_pairs": len(self.retriever.qa_indices),
            "conversation_turns": len(
                self.conversation_history
            ) // 2,
            "fast_path_enabled": self.use_fast_path,
        }