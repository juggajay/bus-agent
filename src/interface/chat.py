"""Chat interface for conversational exploration."""

from typing import List, Dict, Any, Optional
from uuid import UUID
import json

from anthropic import AsyncAnthropic

from ..database import (
    Conversation, Message,
    ProcessedSignal, PatternMatch, Opportunity,
    get_database
)
from ..processors import get_embedding_generator, find_similar_signals
from ..reasoning.prompts import CHAT_SYSTEM_PROMPT
from ..utils import get_settings, get_logger, get_rate_limiter

logger = get_logger(__name__)


class ChatInterface:
    """Conversational interface for exploring opportunities."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = get_rate_limiter("anthropic")
        self.db = get_database()
        self.embedding_generator = get_embedding_generator()

    async def start_conversation(
        self,
        context_type: str = "exploration",
        related_opportunity_id: Optional[UUID] = None
    ) -> Conversation:
        """Start a new conversation."""
        return await self.db.create_conversation(
            context_type=context_type,
            related_opportunity_id=related_opportunity_id
        )

    async def send_message(
        self,
        conversation_id: UUID,
        user_message: str
    ) -> str:
        """
        Send a message and get a response.

        Args:
            conversation_id: ID of the conversation
            user_message: User's message

        Returns:
            Assistant's response
        """
        try:
            # Store user message
            await self.db.add_message(
                conversation_id=conversation_id,
                role="user",
                content=user_message
            )

            # Get conversation history
            messages = await self.db.get_conversation_messages(conversation_id)

            # Get relevant context
            context = await self._get_relevant_context(user_message)

            # Build message history for Claude
            claude_messages = []
            for msg in messages:
                claude_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

            # Generate response
            await self.rate_limiter.acquire()

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                system=CHAT_SYSTEM_PROMPT + f"\n\nCurrent context:\n{context}",
                messages=claude_messages
            )

            assistant_message = response.content[0].text

            # Store assistant message
            await self.db.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_message
            )

            return assistant_message

        except Exception as e:
            logger.error("Chat failed", error=str(e))
            error_msg = "I apologize, but I encountered an error processing your request. Please try again."
            await self.db.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=error_msg
            )
            return error_msg

    async def _get_relevant_context(self, query: str) -> str:
        """Get relevant signals and opportunities for context."""
        context_parts = []

        try:
            # Generate embedding for query
            query_embedding = await self.embedding_generator.generate(query)

            if query_embedding:
                # Search for similar signals
                similar_signals = await self.db.search_signals_by_embedding(
                    query_embedding,
                    limit=5,
                    threshold=0.6
                )

                if similar_signals:
                    context_parts.append("RELEVANT SIGNALS:")
                    for s in similar_signals:
                        context_parts.append(f"- {s.title}: {s.summary}")

            # Get recent patterns
            patterns = await self.db.get_patterns(status="new", min_score=0.5)
            if patterns:
                context_parts.append("\nRECENT PATTERNS:")
                for p in patterns[:5]:
                    context_parts.append(f"- {p.title} ({p.pattern_type}): {p.hypothesis}")

            # Get recent opportunities
            opportunities = await self.db.get_opportunities(status="new")
            if opportunities:
                context_parts.append("\nRECENT OPPORTUNITIES:")
                for o in opportunities[:5]:
                    context_parts.append(f"- {o.title} ({o.timing_stage}): {o.summary}")

        except Exception as e:
            logger.warning("Failed to get context", error=str(e))

        return "\n".join(context_parts) if context_parts else "No specific context available."

    async def ask_about_opportunity(
        self,
        opportunity_id: UUID,
        question: str
    ) -> str:
        """
        Ask a specific question about an opportunity.

        Args:
            opportunity_id: ID of the opportunity
            question: Question to ask

        Returns:
            Response about the opportunity
        """
        # Start conversation with opportunity context
        conversation = await self.start_conversation(
            context_type="opportunity_exploration",
            related_opportunity_id=opportunity_id
        )

        # Get opportunity details
        opportunities = await self.db.get_opportunities()
        opportunity = next((o for o in opportunities if o.id == opportunity_id), None)

        if not opportunity:
            return "Opportunity not found."

        # Enhance question with opportunity context
        enhanced_question = f"""
I'm asking about this opportunity:
Title: {opportunity.title}
Summary: {opportunity.summary}
Timing: {opportunity.timing_stage}
Primary Thesis: {opportunity.primary_thesis}

My question: {question}
"""

        return await self.send_message(conversation.id, enhanced_question)

    async def explore_thesis(self, thesis_element: str) -> str:
        """
        Explore signals and opportunities related to a thesis element.

        Args:
            thesis_element: One of the thesis elements to explore

        Returns:
            Analysis of signals related to this thesis
        """
        conversation = await self.start_conversation(context_type="thesis_exploration")

        question = f"""
Analyze our current signals and opportunities through the lens of the "{thesis_element}" thesis element.

What patterns do we see? What opportunities align with this thesis? What are we missing?
"""

        return await self.send_message(conversation.id, question)


# Singleton
_chat: Optional[ChatInterface] = None


def get_chat_interface() -> ChatInterface:
    """Get chat interface singleton."""
    global _chat
    if _chat is None:
        _chat = ChatInterface()
    return _chat
