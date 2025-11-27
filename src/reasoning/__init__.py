"""Reasoning and synthesis module."""

from .prompts import (
    OPPORTUNITY_GENERATION_PROMPT,
    QUARTERLY_SYNTHESIS_PROMPT,
    CHAT_SYSTEM_PROMPT,
    DIGEST_GENERATION_PROMPT
)
from .opportunity_generator import OpportunityGenerator, get_opportunity_generator
from .synthesis import Synthesizer, get_synthesizer

__all__ = [
    "OPPORTUNITY_GENERATION_PROMPT",
    "QUARTERLY_SYNTHESIS_PROMPT",
    "CHAT_SYSTEM_PROMPT",
    "DIGEST_GENERATION_PROMPT",
    "OpportunityGenerator", "get_opportunity_generator",
    "Synthesizer", "get_synthesizer"
]
