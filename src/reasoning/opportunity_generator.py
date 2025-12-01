"""Opportunity generation from patterns - Solo SaaS Finder v2.0"""

from typing import List, Optional, Dict, Any
from uuid import UUID
import json

from anthropic import AsyncAnthropic

from ..database import (
    PatternMatch, ProcessedSignal,
    OpportunityCreate, Opportunity,
    get_database
)
from ..utils import get_settings, get_logger, get_rate_limiter
from .prompts import OPPORTUNITY_GENERATION_PROMPT

logger = get_logger(__name__)


class OpportunityGenerator:
    """Generate SaaS/directory business opportunities from detected patterns."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = get_rate_limiter("anthropic")
        self.db = get_database()
        self._last_error = None
        self._errors = []

    async def generate_from_pattern(
        self,
        pattern: PatternMatch,
        signals: List[ProcessedSignal]
    ) -> Optional[Opportunity]:
        """
        Generate a SaaS/directory opportunity from a detected pattern.

        Args:
            pattern: The pattern to analyze
            signals: Related signals for context

        Returns:
            Generated and stored opportunity, or None if generation fails
        """
        try:
            await self.rate_limiter.acquire()

            # Format pattern details
            pattern_details = {
                "type": pattern.pattern_type,
                "title": pattern.title,
                "description": pattern.description,
                "hypothesis": pattern.hypothesis,
                "confidence": pattern.confidence_score,
                "opportunity_score": pattern.opportunity_score,
                "primary_thesis": pattern.primary_thesis_alignment
            }

            # Format signals with new SaaS-focused fields
            formatted_signals = [{
                "type": s.signal_type,
                "title": s.title,
                "summary": s.summary,
                "problem_summary": getattr(s, 'problem_summary', '') or '',
                "demand_evidence_level": getattr(s, 'demand_evidence_level', '') or '',
                "keywords": s.keywords,
                "entities": s.entities.model_dump() if s.entities else {},
                "thesis_scores": s.thesis_scores.model_dump() if s.thesis_scores else {},
                "timing_stage": s.timing_stage,
                "velocity": s.velocity_score,
                "novelty": s.novelty_score,
                "is_disqualified": getattr(s, 'is_disqualified', False)
            } for s in signals[:10] if not getattr(s, 'is_disqualified', False)]

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": OPPORTUNITY_GENERATION_PROMPT.format(
                        pattern_details=json.dumps(pattern_details, indent=2),
                        formatted_signals=json.dumps(formatted_signals, indent=2)
                    )
                }]
            )

            # Parse response
            response_text = response.content[0].text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            result = json.loads(response_text)

            # Extract nested fields
            problem = result.get("problem", {})
            solution = result.get("solution", {})
            demand_evidence = result.get("demand_evidence", {})
            competition = result.get("competition", {})
            build_assessment = result.get("build_assessment", {})
            monetisation = result.get("monetisation", {})
            go_to_market = result.get("go_to_market", {})
            scoring = result.get("scoring", {})

            # Create opportunity with new SaaS-focused fields
            opportunity_create = OpportunityCreate(
                title=result.get("business_name", pattern.title),
                business_name=result.get("business_name"),
                one_liner=result.get("one_liner"),
                summary=result.get("one_liner"),

                # Problem/Solution
                problem_description=problem.get("description"),
                target_customer=problem.get("target_customer"),
                current_solutions=problem.get("current_solutions"),
                proposed_solution=solution.get("description"),
                core_features=solution.get("core_features", []),

                # Demand evidence
                demand_evidence=json.dumps(demand_evidence.get("signals", [])),
                demand_strength=demand_evidence.get("strength"),

                # Competition
                competitors=competition.get("competitors", []),
                competition_weakness=competition.get("why_beatable"),

                # Build assessment
                tech_stack_recommendation=build_assessment.get("tech_stack"),
                build_time_estimate=build_assessment.get("estimated_time"),
                technical_challenges=build_assessment.get("challenges", []),
                can_ship_in_4_weeks=build_assessment.get("can_ship_in_4_weeks", True),

                # Monetisation
                pricing_model=monetisation.get("model"),
                suggested_price_points=monetisation.get("price_points"),
                who_pays=monetisation.get("who_pays"),

                # Go-to-market
                customer_channels=go_to_market.get("customer_channels", []),
                first_customers_strategy=go_to_market.get("first_10_customers"),
                seo_potential=go_to_market.get("seo_potential"),

                # Scoring
                pattern_ids=[pattern.id],
                signal_ids=list(pattern.signal_ids) if pattern.signal_ids else [],
                opportunity_type=result.get("opportunity_type", "micro_saas"),
                industries=result.get("industries", self._extract_industries(signals)),
                geographies=self._extract_geographies(signals),
                thesis_scores=scoring,
                overall_score=scoring.get("overall_score"),

                # Verdict
                verdict=result.get("verdict"),
                first_steps=result.get("first_steps", []),

                # Legacy fields for compatibility
                detailed_analysis=json.dumps({
                    "problem": problem,
                    "solution": solution,
                    "demand_evidence": demand_evidence,
                    "competition": competition,
                    "build_assessment": build_assessment,
                    "monetisation": monetisation,
                    "go_to_market": go_to_market
                }),
                primary_thesis=self._determine_primary_thesis(scoring),
                execution_fit_reasoning=result.get("verdict_reasoning", ""),
                timing_stage=result.get("timing_stage", "emerging"),
                existing_players=competition.get("competitors", []),
                incumbent_weakness=competition.get("why_beatable", ""),
                estimated_complexity=self._estimate_complexity(build_assessment),
                key_requirements=build_assessment.get("challenges", []),
                potential_moats=[solution.get("differentiation", "")] if solution.get("differentiation") else [],
                risks=result.get("risks", [])
            )

            # Store opportunity
            opportunity = await self.db.insert_opportunity(opportunity_create)

            logger.info(
                f"Generated opportunity",
                opportunity_id=str(opportunity.id),
                title=opportunity.title,
                verdict=result.get("verdict")
            )

            return opportunity

        except json.JSONDecodeError as e:
            logger.error("Failed to parse opportunity response", error=str(e), response_text=response_text[:500] if 'response_text' in locals() else "N/A")
            self._last_error = f"JSON parse error: {str(e)}"
            return None
        except Exception as e:
            logger.error("Opportunity generation failed", error=str(e), error_type=type(e).__name__)
            self._last_error = f"{type(e).__name__}: {str(e)}"
            return None

    async def generate_from_patterns(
        self,
        patterns: List[PatternMatch],
        signals: List[ProcessedSignal],
        min_score: float = 0.5
    ) -> List[Opportunity]:
        """
        Generate opportunities from multiple patterns.

        Args:
            patterns: Patterns to analyze
            signals: All signals for context
            min_score: Minimum opportunity score to consider

        Returns:
            List of generated opportunities
        """
        opportunities = []

        # Filter patterns by score and skip disqualified signals
        high_score_patterns = [
            p for p in patterns
            if p.opportunity_score >= min_score
        ]

        logger.info(f"Processing {len(high_score_patterns)} high-score patterns from {len(patterns)} total")

        # Build a set of signal IDs for faster lookup
        signal_map = {s.id: s for s in signals}
        logger.info(f"Built signal map with {len(signal_map)} signals")

        # Debug: Check types
        if signals and high_score_patterns:
            sample_signal_id = signals[0].id
            sample_pattern_signal_id = high_score_patterns[0].signal_ids[0] if high_score_patterns[0].signal_ids else None
            logger.info(f"Type of signal.id: {type(sample_signal_id)}")
            logger.info(f"Type of pattern.signal_ids[0]: {type(sample_pattern_signal_id)}")
            if sample_pattern_signal_id:
                logger.info(f"Sample match check: {sample_pattern_signal_id in signal_map}")

        for i, pattern in enumerate(high_score_patterns):
            # Get related signals, excluding disqualified ones
            related_signals = [
                signal_map[sid] for sid in (pattern.signal_ids or [])
                if sid in signal_map and not getattr(signal_map[sid], 'is_disqualified', False)
            ]

            logger.info(f"Pattern {i+1}/{len(high_score_patterns)}: {len(related_signals)} related signals from {len(pattern.signal_ids or [])} signal_ids")

            # Skip if all related signals are disqualified
            if not related_signals:
                logger.info(f"Skipping pattern {pattern.id} - all signals disqualified or not found")
                continue

            opportunity = await self.generate_from_pattern(pattern, related_signals)
            if opportunity:
                opportunities.append(opportunity)
                logger.info(f"Generated opportunity: {opportunity.title}")
            else:
                error_msg = self._last_error or "Unknown error"
                logger.warning(f"Failed to generate opportunity for pattern {pattern.id}: {error_msg}")
                self._errors.append({"pattern_id": str(pattern.id), "error": error_msg})

        return opportunities

    def get_errors(self) -> list:
        """Get list of errors from last generation run."""
        return self._errors

    def clear_errors(self) -> None:
        """Clear error list."""
        self._errors = []

    def _extract_industries(self, signals: List[ProcessedSignal]) -> List[str]:
        """Extract unique industries from signals."""
        industries = set()
        for s in signals:
            if s.entities and s.entities.industries:
                industries.update(s.entities.industries)
        return list(industries)[:10]

    def _extract_geographies(self, signals: List[ProcessedSignal]) -> List[str]:
        """Extract unique geographies from signals."""
        geographies = set()
        for s in signals:
            if s.geography:
                geographies.add(s.geography)
            if s.entities and s.entities.locations:
                geographies.update(s.entities.locations)
        return list(geographies)[:5]

    def _estimate_complexity(self, build_assessment: Dict[str, Any]) -> str:
        """Estimate complexity based on build assessment."""
        can_ship = build_assessment.get("can_ship_in_4_weeks", True)
        challenges = build_assessment.get("challenges", [])

        if can_ship and len(challenges) <= 1:
            return "low"
        elif can_ship and len(challenges) <= 3:
            return "medium"
        else:
            return "high"

    def _determine_primary_thesis(self, scoring: Dict[str, Any]) -> str:
        """Determine the primary thesis factor based on scores."""
        factors = [
            ("demand_evidence", scoring.get("demand_evidence", 0)),
            ("competition_gap", scoring.get("competition_gap", 0)),
            ("trend_timing", scoring.get("trend_timing", 0)),
            ("solo_buildability", scoring.get("solo_buildability", 0)),
            ("clear_monetisation", scoring.get("clear_monetisation", 0)),
            ("regulatory_simplicity", scoring.get("regulatory_simplicity", 0)),
        ]

        # Find the highest scoring factor
        best_factor = max(factors, key=lambda x: x[1] if x[1] else 0)
        return best_factor[0]


# Singleton
_generator: Optional[OpportunityGenerator] = None


def get_opportunity_generator() -> OpportunityGenerator:
    """Get opportunity generator singleton."""
    global _generator
    if _generator is None:
        _generator = OpportunityGenerator()
    return _generator
