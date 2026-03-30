"""
Settings Management for NUST Admission Assistant
================================================
Manages tunable parameters for LLM, retrieval, and prompts
"""

from dataclasses import dataclass, asdict
from typing import Optional
import json


@dataclass
class RetrieverSettings:
    """Retrieval pipeline settings"""
    top_k: int = 3  # Number of results to retrieve
    bm25_weight: float = 0.45  # Weight for BM25 keyword search
    vector_weight: float = 0.55  # Weight for semantic search
    qa_threshold: float = 0.78  # Threshold for direct Q&A answers


@dataclass
class LLMSettings:
    """LLM generation settings"""
    temperature: float = 0.3  # 0.0 = deterministic, 1.0 = creative
    num_ctx: int = 4096  # Context window size (Llama 3.2 supports up to 8192)
    num_predict: int = 1024  # Max tokens to generate
    keep_tokens: int = 64  # Number of tokens to keep from context
    top_p: float = 0.9  # Nucleus sampling parameter
    top_k_sampling: int = 40  # Top-K sampling parameter


@dataclass
class PromptSettings:
    """Prompt and system message settings"""
    system_prompt: Optional[str] = None  # Custom system prompt (None = use default)
    use_distilled: bool = True  # Use distilled prompt for faster inference
    include_history: bool = True  # Include conversation history


@dataclass
class Settings:
    """Complete settings configuration"""
    retriever: RetrieverSettings
    llm: LLMSettings
    prompt: PromptSettings

    def to_dict(self):
        return {
            "retriever": asdict(self.retriever),
            "llm": asdict(self.llm),
            "prompt": asdict(self.prompt),
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            retriever=RetrieverSettings(**data.get("retriever", {})),
            llm=LLMSettings(**data.get("llm", {})),
            prompt=PromptSettings(**data.get("prompt", {})),
        )

    @classmethod
    def default(cls):
        """Returns default settings"""
        return cls(
            retriever=RetrieverSettings(),
            llm=LLMSettings(),
            prompt=PromptSettings(),
        )


class SettingsManager:
    """Manages settings state"""

    def __init__(self):
        self.settings = Settings.default()

    def get_settings(self) -> Settings:
        """Get current settings"""
        return self.settings

    def update_settings(self, updates: dict) -> Settings:
        """
        Update settings from a dictionary.
        
        Example:
            {
                "llm": {"temperature": 0.5, "num_ctx": 2048},
                "retriever": {"top_k": 5},
                "prompt": {"system_prompt": "Custom prompt..."}
            }
        """
        if "retriever" in updates:
            for key, value in updates["retriever"].items():
                if hasattr(self.settings.retriever, key):
                    setattr(self.settings.retriever, key, value)

        if "llm" in updates:
            for key, value in updates["llm"].items():
                if hasattr(self.settings.llm, key):
                    setattr(self.settings.llm, key, value)

        if "prompt" in updates:
            for key, value in updates["prompt"].items():
                if hasattr(self.settings.prompt, key):
                    setattr(self.settings.prompt, key, value)

        return self.settings

    def reset_to_defaults(self) -> Settings:
        """Reset all settings to defaults"""
        self.settings = Settings.default()
        return self.settings
