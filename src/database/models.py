"""Database models and Pydantic schemas."""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from enum import Enum


class SignalStatus(str, Enum):
    """Status of a processed signal."""
    NEW = "new"
    PROCESSED = "processed"
    FAILED = "failed"


class PatternStatus(str, Enum):
    """Status of a detected pattern."""
    NEW = "new"
    REVIEWED = "reviewed"
    INVESTIGATING = "investigating"
    ARCHIVED = "archived"


class OpportunityStatus(str, Enum):
    """Status of an opportunity."""
    NEW = "new"
    EXPLORING = "exploring"
    VALIDATING = "validating"
    PURSUING = "pursuing"
    PASSED = "passed"


class TimingStage(str, Enum):
    """Timing stage of an opportunity."""
    EARLY = "early"
    EMERGING = "emerging"
    GROWING = "growing"
    CROWDED = "crowded"


class OpportunityVerdict(str, Enum):
    """Verdict for an opportunity."""
    BUILD_NOW = "BUILD NOW"
    EXPLORE = "EXPLORE"
    MONITOR = "MONITOR"
    PASS = "PASS"


class RunStatus(str, Enum):
    """Status of a collection or analysis run."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# Raw Signal Models
class RawSignalCreate(BaseModel):
    """Schema for creating a raw signal."""
    source_type: str
    source_category: str
    source_url: Optional[str] = None
    raw_content: Dict[str, Any]
    signal_date: Optional[date] = None
    geography: Optional[str] = None


class RawSignal(RawSignalCreate):
    """Complete raw signal with database fields."""
    id: UUID = Field(default_factory=uuid4)
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# New Thesis Scores for Solo SaaS Finder v2.0
class ThesisScores(BaseModel):
    """Thesis alignment scores - Solo SaaS Finder v2.0"""
    demand_evidence: Optional[int] = None
    competition_gap: Optional[int] = None
    trend_timing: Optional[int] = None
    solo_buildability: Optional[int] = None
    clear_monetisation: Optional[int] = None
    regulatory_simplicity: Optional[int] = None


class EntityExtraction(BaseModel):
    """Extracted entities from a signal."""
    companies: List[str] = []
    technologies: List[str] = []
    industries: List[str] = []
    locations: List[str] = []


class ProcessedSignalCreate(BaseModel):
    """Schema for creating a processed signal."""
    raw_signal_id: UUID
    signal_type: Optional[str] = None
    signal_subtype: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    # New field for SaaS focus
    problem_summary: Optional[str] = None
    demand_evidence_level: Optional[str] = None  # high/medium/low/none
    entities: EntityExtraction = Field(default_factory=EntityExtraction)
    keywords: List[str] = []
    thesis_scores: ThesisScores = Field(default_factory=ThesisScores)
    thesis_reasoning: Optional[str] = None
    novelty_score: Optional[float] = None
    velocity_score: Optional[float] = None
    geography: Optional[str] = None
    timing_stage: Optional[str] = None
    # Disqualification tracking
    is_disqualified: bool = False
    disqualification_reason: Optional[str] = None


class ProcessedSignal(ProcessedSignalCreate):
    """Complete processed signal with database fields."""
    id: UUID = Field(default_factory=uuid4)
    embedding: Optional[List[float]] = None
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Pattern Models
class PatternMatchCreate(BaseModel):
    """Schema for creating a pattern match."""
    pattern_type: str
    signal_ids: List[UUID]
    signal_count: int
    title: str
    description: Optional[str] = None
    hypothesis: Optional[str] = None
    confidence_score: float
    opportunity_score: float
    primary_thesis_alignment: Optional[str] = None
    thesis_scores: Dict[str, Any] = {}


class PatternMatch(PatternMatchCreate):
    """Complete pattern match with database fields."""
    id: UUID = Field(default_factory=uuid4)
    status: PatternStatus = PatternStatus.NEW
    user_notes: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Opportunity Models - Updated for SaaS focus
class OpportunityCreate(BaseModel):
    """Schema for creating an opportunity."""
    title: str
    # New SaaS-focused fields
    business_name: Optional[str] = None
    one_liner: Optional[str] = None
    summary: Optional[str] = None
    detailed_analysis: Optional[str] = None
    # Problem/Solution
    problem_description: Optional[str] = None
    target_customer: Optional[str] = None
    current_solutions: Optional[str] = None
    proposed_solution: Optional[str] = None
    core_features: List[str] = []
    # Evidence
    demand_evidence: Optional[str] = None
    demand_strength: Optional[str] = None  # strong/moderate/weak
    # Competition
    competitors: List[str] = []
    competition_weakness: Optional[str] = None
    # Build assessment
    tech_stack_recommendation: Optional[str] = None
    build_time_estimate: Optional[str] = None
    technical_challenges: List[str] = []
    can_ship_in_4_weeks: bool = True
    # Monetisation
    pricing_model: Optional[str] = None
    suggested_price_points: Optional[str] = None
    who_pays: Optional[str] = None
    # Go-to-market
    customer_channels: List[str] = []
    first_customers_strategy: Optional[str] = None
    seo_potential: Optional[str] = None
    # Scoring
    pattern_ids: List[UUID] = []
    signal_ids: List[UUID] = []
    opportunity_type: Optional[str] = None  # vertical_saas, directory, micro_saas, etc.
    industries: List[str] = []
    geographies: List[str] = []
    thesis_scores: Dict[str, Any] = {}
    overall_score: Optional[float] = None  # Changed to float for v2.0 LLM scoring
    # Verdict
    verdict: Optional[str] = None  # BUILD NOW, EXPLORE, MONITOR, PASS
    first_steps: List[str] = []
    # Legacy fields for compatibility
    primary_thesis: Optional[str] = None
    execution_fit_reasoning: Optional[str] = None
    timing_stage: Optional[str] = None
    time_sensitivity: Optional[str] = None
    existing_players: List[str] = []
    incumbent_weakness: Optional[str] = None
    estimated_complexity: Optional[str] = None
    key_requirements: List[str] = []
    potential_moats: List[str] = []
    risks: List[str] = []


class Opportunity(OpportunityCreate):
    """Complete opportunity with database fields."""
    id: UUID = Field(default_factory=uuid4)
    status: OpportunityStatus = OpportunityStatus.NEW
    user_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Collection Run Models
class CollectionRunCreate(BaseModel):
    """Schema for creating a collection run."""
    source_type: str


class CollectionRun(CollectionRunCreate):
    """Complete collection run with database fields."""
    id: UUID = Field(default_factory=uuid4)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: RunStatus = RunStatus.RUNNING
    signals_collected: int = 0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Analysis Run Models
class AnalysisRunCreate(BaseModel):
    """Schema for creating an analysis run."""
    run_type: str  # 'weekly', 'monthly', 'quarterly', 'anomaly'


class AnalysisRun(AnalysisRunCreate):
    """Complete analysis run with database fields."""
    id: UUID = Field(default_factory=uuid4)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: RunStatus = RunStatus.RUNNING
    patterns_detected: int = 0
    opportunities_generated: int = 0
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Conversation Models
class ConversationCreate(BaseModel):
    """Schema for creating a conversation."""
    context_type: Optional[str] = None
    related_opportunity_id: Optional[UUID] = None


class Conversation(ConversationCreate):
    """Complete conversation with database fields."""
    id: UUID = Field(default_factory=uuid4)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MessageCreate(BaseModel):
    """Schema for creating a message."""
    conversation_id: UUID
    role: str  # 'user' or 'assistant'
    content: str
    context_signals: List[UUID] = []


class Message(MessageCreate):
    """Complete message with database fields."""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Digest Models
class DigestContent(BaseModel):
    """Content for a periodic digest."""
    period: str  # 'weekly', 'monthly', 'quarterly'
    generated_at: datetime
    signals_processed: int
    patterns_detected: int
    opportunities_identified: int
    top_patterns: List[Dict[str, Any]]
    new_opportunities: List[Dict[str, Any]]
    velocity_spikes: List[Dict[str, Any]]
    key_insight: str
    recommended_actions: List[str]
    # New fields for SaaS digest
    top_build_ready_ideas: List[Dict[str, Any]] = []
    emerging_trends: List[Dict[str, Any]] = []
    pass_list: List[Dict[str, Any]] = []
    this_week_action: Optional[str] = None
