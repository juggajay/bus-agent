"""Database module."""

from .models import (
    RawSignal, RawSignalCreate,
    ProcessedSignal, ProcessedSignalCreate,
    PatternMatch, PatternMatchCreate,
    Opportunity, OpportunityCreate,
    CollectionRun, AnalysisRun,
    Conversation, Message,
    ThesisScores, EntityExtraction,
    DigestContent,
    SignalStatus, PatternStatus, OpportunityStatus, TimingStage, RunStatus
)
from .queries import Database, get_database

__all__ = [
    "RawSignal", "RawSignalCreate",
    "ProcessedSignal", "ProcessedSignalCreate",
    "PatternMatch", "PatternMatchCreate",
    "Opportunity", "OpportunityCreate",
    "CollectionRun", "AnalysisRun",
    "Conversation", "Message",
    "ThesisScores", "EntityExtraction",
    "DigestContent",
    "SignalStatus", "PatternStatus", "OpportunityStatus", "TimingStage", "RunStatus",
    "Database", "get_database"
]
