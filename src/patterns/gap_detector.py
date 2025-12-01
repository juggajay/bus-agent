"""Gap detection - finding complaints without solutions."""

from typing import List, Dict, Optional
from uuid import UUID
import json

from anthropic import AsyncAnthropic

from ..database import ProcessedSignal, PatternMatchCreate, get_database
from ..processors import find_similar_signals, average_embedding
from ..utils import get_settings, get_logger, get_rate_limiter

logger = get_logger(__name__)

GAP_ANALYSIS_PROMPT = """You are analyzing a potential market gap - complaints or problems that don't appear to have solutions being built.

COMPLAINTS/PROBLEMS:
{complaints}

EXISTING BUILDER ACTIVITY (if any):
{builder_activity}

Analyze this potential gap:
1. Is this a real gap or are there solutions being built/available?
2. Why might this gap exist?
3. What would a solution look like?
4. How severe is the pain point for users?
5. Is this gap worth pursuing?

Respond ONLY with valid JSON:
{{
    "is_real_gap": true/false,
    "gap_title": "short title",
    "gap_description": "description of the gap",
    "pain_severity": 1-10,
    "existing_solutions": ["solution 1", "solution 2"],
    "solution_hypothesis": "what a solution might look like",
    "why_gap_exists": "explanation",
    "worth_pursuing": true/false,
    "confidence": 0.0-1.0
}}"""


class GapDetector:
    """Detect gaps between complaints and solutions."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = get_rate_limiter("anthropic")
        self.db = get_database()

    async def detect(
        self,
        signals: List[ProcessedSignal],
        similarity_threshold: float = 0.75
    ) -> List[PatternMatchCreate]:
        """
        Detect gap patterns by finding complaints without corresponding builder activity.

        Args:
            signals: List of processed signals
            similarity_threshold: Threshold for matching complaints to builder activity

        Returns:
            List of detected gap patterns
        """
        # Separate signals by type
        complaint_signals = [s for s in signals if s.signal_type == "complaint"]
        builder_signals = [s for s in signals if s.signal_type == "builder_activity"]

        if not complaint_signals:
            return []

        # Group complaints by topic
        complaint_clusters = self._cluster_complaints(complaint_signals)

        patterns = []
        for cluster in complaint_clusters:
            if len(cluster) < 1:  # Allow single complaints to form gaps
                continue

            # Check if there's builder activity addressing this
            cluster_embedding = average_embedding([s.embedding for s in cluster if s.embedding])

            if cluster_embedding:
                builder_matches = find_similar_signals(
                    cluster_embedding,
                    [s.embedding for s in builder_signals if s.embedding],
                    threshold=similarity_threshold
                )
            else:
                builder_matches = []

            # If few or no builder matches, this is potentially a gap
            if len(builder_matches) <= 1:
                pattern = await self._analyze_gap(cluster, builder_signals[:3] if builder_matches else [])
                if pattern:
                    patterns.append(pattern)

        return patterns

    def _cluster_complaints(
        self,
        complaints: List[ProcessedSignal]
    ) -> List[List[ProcessedSignal]]:
        """Cluster complaints by topic similarity."""
        # Simple keyword-based clustering
        clusters: Dict[str, List[ProcessedSignal]] = {}

        for complaint in complaints:
            # Use first keyword as cluster key
            if complaint.keywords and len(complaint.keywords) > 0:
                key = complaint.keywords[0].lower()
            else:
                key = "general"

            if key not in clusters:
                clusters[key] = []
            clusters[key].append(complaint)

        return list(clusters.values())

    async def _analyze_gap(
        self,
        complaints: List[ProcessedSignal],
        related_builder_activity: List[ProcessedSignal]
    ) -> Optional[PatternMatchCreate]:
        """Analyze a potential gap with LLM."""
        try:
            await self.rate_limiter.acquire()

            # Format data for prompt
            complaint_data = [{
                "title": c.title,
                "summary": c.summary,
                "keywords": c.keywords
            } for c in complaints[:5]]

            builder_data = [{
                "title": b.title,
                "summary": b.summary,
                "keywords": b.keywords
            } for b in related_builder_activity]

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{
                    "role": "user",
                    "content": GAP_ANALYSIS_PROMPT.format(
                        complaints=json.dumps(complaint_data, indent=2),
                        builder_activity=json.dumps(builder_data, indent=2) if builder_data else "None found"
                    )
                }]
            )

            # Parse response
            response_text = response.content[0].text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            result = json.loads(response_text)

            # Only create pattern if it's a real gap worth pursuing
            if not result.get("is_real_gap", False):
                return None

            if not result.get("worth_pursuing", False):
                return None

            confidence = float(result.get("confidence", 0.5))
            pain_severity = int(result.get("pain_severity", 5))

            # Calculate opportunity score
            opportunity_score = (confidence * pain_severity / 10) * min(1.0, len(complaints) / 3)

            # Aggregate thesis scores from complaints
            thesis_scores = self._aggregate_thesis_scores(complaints)

            # Gaps with high demand evidence score higher
            if thesis_scores.get("demand_evidence") and thesis_scores["demand_evidence"] >= 7:
                opportunity_score *= 1.2

            primary_thesis = max(thesis_scores.items(), key=lambda x: x[1] or 0)[0]

            return PatternMatchCreate(
                pattern_type="gap",
                signal_ids=[s.id for s in complaints],
                signal_count=len(complaints),
                title=f"Gap: {result.get('gap_title', 'Unaddressed Problem')}",
                description=result.get("gap_description", ""),
                hypothesis=result.get("solution_hypothesis", ""),
                confidence_score=confidence,
                opportunity_score=min(1.0, opportunity_score),
                primary_thesis_alignment=primary_thesis,
                thesis_scores=thesis_scores
            )

        except json.JSONDecodeError as e:
            logger.error("Failed to parse gap analysis", error=str(e))
            return None
        except Exception as e:
            logger.error("Gap analysis failed", error=str(e))
            return None

    def _aggregate_thesis_scores(self, signals: List[ProcessedSignal]) -> Dict[str, float]:
        """Aggregate thesis scores across signals - Solo SaaS Finder v2.0."""
        scores = {
            "demand_evidence": [],
            "competition_gap": [],
            "trend_timing": [],
            "solo_buildability": [],
            "clear_monetisation": [],
            "regulatory_simplicity": []
        }

        for s in signals:
            if s.thesis_scores:
                if s.thesis_scores.demand_evidence:
                    scores["demand_evidence"].append(s.thesis_scores.demand_evidence)
                if s.thesis_scores.competition_gap:
                    scores["competition_gap"].append(s.thesis_scores.competition_gap)
                if s.thesis_scores.trend_timing:
                    scores["trend_timing"].append(s.thesis_scores.trend_timing)
                if s.thesis_scores.solo_buildability:
                    scores["solo_buildability"].append(s.thesis_scores.solo_buildability)
                if s.thesis_scores.clear_monetisation:
                    scores["clear_monetisation"].append(s.thesis_scores.clear_monetisation)
                if s.thesis_scores.regulatory_simplicity:
                    scores["regulatory_simplicity"].append(s.thesis_scores.regulatory_simplicity)

        return {
            k: sum(v) / len(v) if v else None
            for k, v in scores.items()
        }


# Singleton
_detector: Optional[GapDetector] = None


def get_gap_detector() -> GapDetector:
    """Get gap detector singleton."""
    global _detector
    if _detector is None:
        _detector = GapDetector()
    return _detector
