"""Chat interface for conversational exploration - Solo SaaS Finder v2.0"""

from typing import List, Dict, Any, Optional
from uuid import UUID
import json

from anthropic import AsyncAnthropic

from ..database import (
    Conversation, Message,
    ProcessedSignal, PatternMatch, Opportunity,
    get_database
)
from ..processors import get_embedding_generator
from ..reasoning.prompts import CHAT_SYSTEM_PROMPT
from ..utils import get_settings, get_logger, get_rate_limiter

logger = get_logger(__name__)


class ChatInterface:
    """Conversational interface for exploring SaaS opportunities."""

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

            # Use the new CHAT_SYSTEM_PROMPT with context
            system_prompt = CHAT_SYSTEM_PROMPT.format(context=context)

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                system=system_prompt,
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
        """Get relevant signals and opportunities for context, filtered for SaaS focus."""
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

                # Filter out disqualified signals
                valid_signals = [
                    s for s in similar_signals
                    if not getattr(s, 'is_disqualified', False)
                ]

                if valid_signals:
                    context_parts.append("RELEVANT SIGNALS:")
                    for s in valid_signals:
                        demand_level = getattr(s, 'demand_evidence_level', 'unknown')
                        problem = getattr(s, 'problem_summary', '') or ''
                        context_parts.append(
                            f"- [{s.signal_type}] {s.title}"
                            f"\n  Summary: {s.summary}"
                            f"\n  Problem: {problem}"
                            f"\n  Demand evidence: {demand_level}"
                        )

            # Get recent patterns
            patterns = await self.db.get_patterns(status="new", min_score=0.5)
            if patterns:
                context_parts.append("\nRECENT PATTERNS:")
                for p in patterns[:5]:
                    context_parts.append(
                        f"- [{p.pattern_type}] {p.title} (score: {p.opportunity_score:.2f})"
                        f"\n  Hypothesis: {p.hypothesis}"
                    )

            # Get recent opportunities with SaaS-focused fields
            opportunities = await self.db.get_opportunities(status="new")
            if opportunities:
                context_parts.append("\nRECENT OPPORTUNITIES:")
                for o in opportunities[:5]:
                    business_name = getattr(o, 'business_name', None) or o.title
                    one_liner = getattr(o, 'one_liner', None) or o.summary
                    verdict = getattr(o, 'verdict', None) or 'N/A'
                    overall_score = getattr(o, 'overall_score', None)
                    build_time = getattr(o, 'build_time_estimate', None) or 'Unknown'

                    context_parts.append(
                        f"- {business_name} ({o.timing_stage}, {o.opportunity_type})"
                        f"\n  {one_liner}"
                        f"\n  Verdict: {verdict}"
                        f"\n  Overall score: {overall_score}/10"
                        f"\n  Build time: {build_time}"
                    )

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

        # Format opportunity with new SaaS-focused fields
        business_name = getattr(opportunity, 'business_name', None) or opportunity.title
        one_liner = getattr(opportunity, 'one_liner', None) or opportunity.summary
        verdict = getattr(opportunity, 'verdict', None) or 'N/A'
        overall_score = getattr(opportunity, 'overall_score', None)
        build_time = getattr(opportunity, 'build_time_estimate', None) or 'Unknown'
        pricing_model = getattr(opportunity, 'pricing_model', None) or 'Not specified'
        first_steps = getattr(opportunity, 'first_steps', [])

        enhanced_question = f"""
I'm asking about this SaaS opportunity:

**Business Name:** {business_name}
**One-liner:** {one_liner}
**Opportunity Type:** {opportunity.opportunity_type}
**Timing Stage:** {opportunity.timing_stage}
**Verdict:** {verdict}
**Overall Score:** {overall_score}/10
**Build Time Estimate:** {build_time}
**Pricing Model:** {pricing_model}
**First Steps:** {', '.join(first_steps[:3]) if first_steps else 'Not specified'}

Full Summary: {opportunity.summary}

My question: {question}
"""

        return await self.send_message(conversation.id, enhanced_question)

    async def explore_scoring_factor(self, factor: str) -> str:
        """
        Explore signals and opportunities related to a scoring factor.

        Args:
            factor: One of the 6 scoring factors to explore

        Returns:
            Analysis of signals related to this factor
        """
        valid_factors = [
            "demand_evidence", "competition_gap", "trend_timing",
            "solo_buildability", "clear_monetisation", "regulatory_simplicity"
        ]

        if factor not in valid_factors:
            return f"Invalid factor. Valid factors are: {', '.join(valid_factors)}"

        conversation = await self.start_conversation(context_type="factor_exploration")

        factor_descriptions = {
            "demand_evidence": "proof people want this and would pay",
            "competition_gap": "whether the space is empty or poorly served",
            "trend_timing": "whether this is the right time to build",
            "solo_buildability": "whether one person can ship this in 2-4 weeks",
            "clear_monetisation": "whether there's an obvious revenue model",
            "regulatory_simplicity": "whether there are regulatory hurdles"
        }

        question = f"""
Analyze our current signals and opportunities through the lens of "{factor}" ({factor_descriptions[factor]}).

Specifically:
1. What patterns show strong {factor}?
2. What opportunities score highest on {factor}?
3. What niches or industries show the best {factor}?
4. What signals should we pay more attention to regarding {factor}?
5. Are there any blind spots we're missing?

Focus on actionable insights for finding SaaS/directory opportunities.
"""

        return await self.send_message(conversation.id, question)

    async def get_build_recommendations(self) -> str:
        """
        Get recommendations for what to build based on current data.

        Returns:
            Recommendations for SaaS/directory ideas to build
        """
        conversation = await self.start_conversation(context_type="build_recommendations")

        question = """
Based on all current signals, patterns, and opportunities, what should I build?

Please give me:
1. Your top 3 "BUILD NOW" recommendations with brief reasoning
2. Any opportunities that are close but need more validation
3. What to avoid (too competitive, too regulated, etc.)
4. The single best opportunity if I had to start this week

Focus on:
- Solo buildable in 2-4 weeks
- Clear demand evidence
- Obvious monetisation
- Weak or no competition
- Not regulated
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
