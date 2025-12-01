"""Database query operations - Solo SaaS Finder v2.0"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
import json

from supabase import create_client, Client
from .models import (
    RawSignal, RawSignalCreate,
    ProcessedSignal, ProcessedSignalCreate,
    PatternMatch, PatternMatchCreate,
    Opportunity, OpportunityCreate,
    CollectionRun, CollectionRunCreate,
    AnalysisRun, AnalysisRunCreate,
    Conversation, ConversationCreate,
    Message, MessageCreate,
    RunStatus
)
from ..utils import get_settings, get_logger

logger = get_logger(__name__)


class Database:
    """Database operations wrapper - Updated for Solo SaaS Finder v2.0"""

    def __init__(self):
        settings = get_settings()
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )

    # Raw Signals
    async def insert_raw_signal(self, signal: RawSignalCreate) -> RawSignal:
        """Insert a new raw signal."""
        data = signal.model_dump()
        data["raw_content"] = json.dumps(data["raw_content"])
        if data.get("signal_date"):
            data["signal_date"] = data["signal_date"].isoformat()

        result = self.client.table("raw_signals").insert(data).execute()

        # Parse raw_content back to dict if it's a string (Supabase returns JSONB as string)
        r = result.data[0]
        if isinstance(r.get("raw_content"), str):
            r["raw_content"] = json.loads(r["raw_content"])
        return RawSignal(**r)

    async def insert_raw_signals_batch(self, signals: List[RawSignalCreate]) -> List[RawSignal]:
        """Insert multiple raw signals in batch."""
        data_list = []
        for signal in signals:
            data = signal.model_dump()
            data["raw_content"] = json.dumps(data["raw_content"])
            if data.get("signal_date"):
                data["signal_date"] = data["signal_date"].isoformat()
            data_list.append(data)

        result = self.client.table("raw_signals").insert(data_list).execute()

        # Parse raw_content back to dict if it's a string (Supabase returns JSONB as string)
        signals_out = []
        for r in result.data:
            if isinstance(r.get("raw_content"), str):
                r["raw_content"] = json.loads(r["raw_content"])
            signals_out.append(RawSignal(**r))
        return signals_out

    async def get_unprocessed_signals(self, limit: int = 100) -> List[RawSignal]:
        """Get raw signals that haven't been processed yet."""
        # First get IDs of already processed signals
        processed_result = self.client.table("processed_signals").select("raw_signal_id").execute()
        processed_ids = [r["raw_signal_id"] for r in processed_result.data]

        # Get raw signals not in processed list
        query = self.client.table("raw_signals").select("*")
        if processed_ids:
            query = query.not_.in_("id", processed_ids)

        result = query.limit(limit).execute()

        # Parse raw_content back to dict if it's a string
        signals = []
        for r in result.data:
            if isinstance(r.get("raw_content"), str):
                r["raw_content"] = json.loads(r["raw_content"])
            signals.append(RawSignal(**r))
        return signals

    async def get_recent_signals(
        self,
        days: int = 7,
        source_type: Optional[str] = None
    ) -> List[RawSignal]:
        """Get signals from the last N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = self.client.table("raw_signals").select("*").gte(
            "collected_at", cutoff.isoformat()
        )
        if source_type:
            query = query.eq("source_type", source_type)

        result = query.order("collected_at", desc=True).execute()

        # Parse raw_content back to dict if it's a string
        signals = []
        for r in result.data:
            if isinstance(r.get("raw_content"), str):
                r["raw_content"] = json.loads(r["raw_content"])
            signals.append(RawSignal(**r))
        return signals

    # Processed Signals - Updated for Solo SaaS Finder v2.0
    def _parse_processed_signal_data(self, data: dict) -> dict:
        """Parse returned processed signal data from Supabase - Updated for v2.0"""
        # Parse entities JSON string back to dict
        if isinstance(data.get("entities"), str):
            data["entities"] = json.loads(data["entities"])

        # Parse embedding JSON string back to list
        if isinstance(data.get("embedding"), str):
            data["embedding"] = json.loads(data["embedding"])

        # Reconstruct thesis_scores from individual columns - NEW v2.0 fields
        thesis_scores = {}
        score_fields = [
            ("score_demand_evidence", "demand_evidence"),
            ("score_competition_gap", "competition_gap"),
            ("score_trend_timing", "trend_timing"),
            ("score_solo_buildability", "solo_buildability"),
            ("score_clear_monetisation", "clear_monetisation"),
            ("score_regulatory_simplicity", "regulatory_simplicity"),
        ]
        for db_field, thesis_field in score_fields:
            if db_field in data:
                thesis_scores[thesis_field] = data.pop(db_field)
        data["thesis_scores"] = thesis_scores

        return data

    async def insert_processed_signal(self, signal: ProcessedSignalCreate, embedding: Optional[List[float]] = None) -> ProcessedSignal:
        """Insert a processed signal with optional embedding - Updated for v2.0"""
        data = signal.model_dump()

        # Convert entities to JSON string
        data["entities"] = json.dumps(data["entities"])
        data["raw_signal_id"] = str(data["raw_signal_id"])

        # Map thesis_scores to individual columns - NEW v2.0 fields
        thesis_scores = data.pop("thesis_scores", {})
        if thesis_scores:
            data["score_demand_evidence"] = thesis_scores.get("demand_evidence")
            data["score_competition_gap"] = thesis_scores.get("competition_gap")
            data["score_trend_timing"] = thesis_scores.get("trend_timing")
            data["score_solo_buildability"] = thesis_scores.get("solo_buildability")
            data["score_clear_monetisation"] = thesis_scores.get("clear_monetisation")
            data["score_regulatory_simplicity"] = thesis_scores.get("regulatory_simplicity")

        if embedding:
            data["embedding"] = embedding

        result = self.client.table("processed_signals").insert(data).execute()
        return ProcessedSignal(**self._parse_processed_signal_data(result.data[0]))

    async def get_processed_signals(
        self,
        days: int = 30,
        signal_type: Optional[str] = None,
        min_thesis_score: Optional[int] = None
    ) -> List[ProcessedSignal]:
        """Get processed signals with optional filters."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = self.client.table("processed_signals").select("*").gte(
            "processed_at", cutoff.isoformat()
        )

        if signal_type:
            query = query.eq("signal_type", signal_type)

        result = query.order("processed_at", desc=True).execute()
        signals = [ProcessedSignal(**self._parse_processed_signal_data(r)) for r in result.data]

        # Filter by thesis score if specified (using new v2.0 fields)
        if min_thesis_score:
            signals = [
                s for s in signals
                if any([
                    (s.thesis_scores.demand_evidence or 0) >= min_thesis_score,
                    (s.thesis_scores.competition_gap or 0) >= min_thesis_score,
                    (s.thesis_scores.trend_timing or 0) >= min_thesis_score,
                    (s.thesis_scores.solo_buildability or 0) >= min_thesis_score,
                    (s.thesis_scores.clear_monetisation or 0) >= min_thesis_score,
                    (s.thesis_scores.regulatory_simplicity or 0) >= min_thesis_score,
                ])
            ]

        return signals

    async def search_signals_by_embedding(
        self,
        embedding: List[float],
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[ProcessedSignal]:
        """Search for similar signals using vector similarity."""
        result = self.client.rpc(
            "match_signals",
            {
                "query_embedding": embedding,
                "match_threshold": threshold,
                "match_count": limit
            }
        ).execute()
        return [ProcessedSignal(**self._parse_processed_signal_data(r)) for r in result.data]

    async def get_recent_embeddings(self, days: int = 7, limit: int = 1000) -> List[List[float]]:
        """Get embeddings from recent signals for novelty detection."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = self.client.table("processed_signals").select(
            "embedding"
        ).gte(
            "processed_at", cutoff.isoformat()
        ).not_.is_("embedding", "null").limit(limit).execute()

        embeddings = []
        for r in result.data:
            emb = r.get("embedding")
            if emb:
                # Parse JSON string if needed
                if isinstance(emb, str):
                    emb = json.loads(emb)
                embeddings.append(emb)
        return embeddings

    # Pattern Matches
    def _parse_pattern_data(self, data: dict) -> dict:
        """Parse returned pattern data from Supabase."""
        if isinstance(data.get("signal_ids"), str):
            data["signal_ids"] = json.loads(data["signal_ids"])
        if isinstance(data.get("thesis_scores"), str):
            data["thesis_scores"] = json.loads(data["thesis_scores"])
        return data

    async def insert_pattern(self, pattern: PatternMatchCreate) -> PatternMatch:
        """Insert a new pattern match."""
        data = pattern.model_dump()
        data["signal_ids"] = [str(sid) for sid in data["signal_ids"]]
        data["thesis_scores"] = json.dumps(data["thesis_scores"])

        result = self.client.table("pattern_matches").insert(data).execute()
        return PatternMatch(**self._parse_pattern_data(result.data[0]))

    async def get_patterns(
        self,
        status: Optional[str] = None,
        min_score: Optional[float] = None
    ) -> List[PatternMatch]:
        """Get patterns with optional filters."""
        query = self.client.table("pattern_matches").select("*")

        if status:
            query = query.eq("status", status)
        if min_score:
            query = query.gte("opportunity_score", min_score)

        result = query.order("detected_at", desc=True).execute()
        return [PatternMatch(**self._parse_pattern_data(r)) for r in result.data]

    async def update_pattern_status(
        self,
        pattern_id: UUID,
        status: str,
        notes: Optional[str] = None
    ) -> PatternMatch:
        """Update a pattern's status."""
        data = {"status": status}
        if notes:
            data["user_notes"] = notes

        result = self.client.table("pattern_matches").update(data).eq(
            "id", str(pattern_id)
        ).execute()
        return PatternMatch(**self._parse_pattern_data(result.data[0]))

    # Opportunities - Updated for Solo SaaS Finder v2.0
    def _parse_opportunity_data(self, data: dict) -> dict:
        """Parse returned opportunity data from Supabase - Updated for v2.0"""
        # Helper to parse JSON or default to empty list
        def parse_list_field(field_name: str) -> list:
            val = data.get(field_name)
            if val is None:
                return []
            if isinstance(val, str):
                return json.loads(val)
            if isinstance(val, list):
                return val
            return []

        # Helper to parse JSON or default to empty dict
        def parse_dict_field(field_name: str) -> dict:
            val = data.get(field_name)
            if val is None:
                return {}
            if isinstance(val, str):
                return json.loads(val)
            if isinstance(val, dict):
                return val
            return {}

        # Parse list fields with defaults for NULL values
        data["pattern_ids"] = parse_list_field("pattern_ids")
        data["signal_ids"] = parse_list_field("signal_ids")
        data["industries"] = parse_list_field("industries")
        data["geographies"] = parse_list_field("geographies")
        data["existing_players"] = parse_list_field("existing_players")
        data["key_requirements"] = parse_list_field("key_requirements")
        data["potential_moats"] = parse_list_field("potential_moats")
        data["risks"] = parse_list_field("risks")
        # New v2.0 list fields
        data["core_features"] = parse_list_field("core_features")
        data["competitors"] = parse_list_field("competitors")
        data["technical_challenges"] = parse_list_field("technical_challenges")
        data["customer_channels"] = parse_list_field("customer_channels")
        data["first_steps"] = parse_list_field("first_steps")
        # Dict field
        data["thesis_scores"] = parse_dict_field("thesis_scores")

        return data

    async def insert_opportunity(self, opportunity: OpportunityCreate) -> Opportunity:
        """Insert a new opportunity."""
        data = opportunity.model_dump()
        data["pattern_ids"] = [str(pid) for pid in data["pattern_ids"]]
        data["signal_ids"] = [str(sid) for sid in data["signal_ids"]]
        data["thesis_scores"] = json.dumps(data["thesis_scores"])

        result = self.client.table("opportunities").insert(data).execute()
        return Opportunity(**self._parse_opportunity_data(result.data[0]))

    async def get_opportunities(
        self,
        status: Optional[str] = None,
        timing_stage: Optional[str] = None
    ) -> List[Opportunity]:
        """Get opportunities with optional filters."""
        query = self.client.table("opportunities").select("*")

        if status:
            query = query.eq("status", status)
        if timing_stage:
            query = query.eq("timing_stage", timing_stage)

        result = query.order("created_at", desc=True).execute()
        return [Opportunity(**self._parse_opportunity_data(r)) for r in result.data]

    async def update_opportunity_status(
        self,
        opportunity_id: UUID,
        status: str,
        notes: Optional[str] = None
    ) -> Opportunity:
        """Update an opportunity's status."""
        data = {"status": status, "updated_at": datetime.utcnow().isoformat()}
        if notes:
            data["user_notes"] = notes

        result = self.client.table("opportunities").update(data).eq(
            "id", str(opportunity_id)
        ).execute()
        return Opportunity(**self._parse_opportunity_data(result.data[0]))

    # Collection Runs
    async def start_collection_run(self, source_type: str) -> CollectionRun:
        """Start a new collection run."""
        data = {"source_type": source_type}
        result = self.client.table("collection_runs").insert(data).execute()
        return CollectionRun(**result.data[0])

    async def complete_collection_run(
        self,
        run_id: UUID,
        signals_collected: int,
        error_message: Optional[str] = None
    ) -> CollectionRun:
        """Complete a collection run."""
        status = RunStatus.COMPLETED if not error_message else RunStatus.FAILED
        data = {
            "completed_at": datetime.utcnow().isoformat(),
            "status": status.value,
            "signals_collected": signals_collected
        }
        if error_message:
            data["error_message"] = error_message

        result = self.client.table("collection_runs").update(data).eq(
            "id", str(run_id)
        ).execute()
        return CollectionRun(**result.data[0])

    # Analysis Runs
    async def start_analysis_run(self, run_type: str) -> AnalysisRun:
        """Start a new analysis run."""
        data = {"run_type": run_type}
        result = self.client.table("analysis_runs").insert(data).execute()
        return AnalysisRun(**result.data[0])

    async def complete_analysis_run(
        self,
        run_id: UUID,
        patterns_detected: int,
        opportunities_generated: int,
        summary: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> AnalysisRun:
        """Complete an analysis run."""
        status = RunStatus.COMPLETED if not error_message else RunStatus.FAILED
        data = {
            "completed_at": datetime.utcnow().isoformat(),
            "status": status.value,
            "patterns_detected": patterns_detected,
            "opportunities_generated": opportunities_generated
        }
        if summary:
            data["summary"] = summary

        result = self.client.table("analysis_runs").update(data).eq(
            "id", str(run_id)
        ).execute()
        return AnalysisRun(**result.data[0])

    # Conversations
    async def create_conversation(
        self,
        context_type: Optional[str] = None,
        related_opportunity_id: Optional[UUID] = None
    ) -> Conversation:
        """Create a new conversation."""
        data = {}
        if context_type:
            data["context_type"] = context_type
        if related_opportunity_id:
            data["related_opportunity_id"] = str(related_opportunity_id)

        result = self.client.table("conversations").insert(data).execute()
        return Conversation(**result.data[0])

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        context_signals: List[UUID] = []
    ) -> Message:
        """Add a message to a conversation."""
        data = {
            "conversation_id": str(conversation_id),
            "role": role,
            "content": content,
            "context_signals": [str(sid) for sid in context_signals]
        }
        result = self.client.table("messages").insert(data).execute()
        return Message(**result.data[0])

    async def get_conversation_messages(self, conversation_id: UUID) -> List[Message]:
        """Get all messages in a conversation."""
        result = self.client.table("messages").select("*").eq(
            "conversation_id", str(conversation_id)
        ).order("created_at", desc=False).execute()
        return [Message(**r) for r in result.data]


# Singleton instance
_db: Optional[Database] = None


def get_database() -> Database:
    """Get database singleton instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db
