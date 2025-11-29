"""FastAPI web interface."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..database import get_database, OpportunityStatus, PatternStatus
from ..collectors import registry, register_all_collectors
from ..processors import get_pipeline
from ..patterns import get_pattern_detector
from ..reasoning import get_opportunity_generator
from .chat import get_chat_interface
from .digest import get_digest_generator
from .alerts import get_alert_system

app = FastAPI(
    title="Opportunity Intelligence Agent",
    description="Automated business opportunity discovery system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str


class OpportunityUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class PatternUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# Signals endpoints
@app.get("/signals")
async def get_signals(
    days: int = Query(default=7, ge=1, le=90),
    signal_type: Optional[str] = None,
    min_thesis_score: Optional[int] = Query(default=None, ge=1, le=10)
):
    """Get processed signals with optional filters."""
    db = get_database()
    signals = await db.get_processed_signals(
        days=days,
        signal_type=signal_type,
        min_thesis_score=min_thesis_score
    )
    return {"signals": [s.model_dump() for s in signals], "count": len(signals)}


# Patterns endpoints
@app.get("/patterns")
async def get_patterns(
    status: Optional[str] = None,
    min_score: Optional[float] = Query(default=None, ge=0, le=1)
):
    """Get detected patterns with optional filters."""
    db = get_database()
    patterns = await db.get_patterns(status=status, min_score=min_score)
    return {"patterns": [p.model_dump() for p in patterns], "count": len(patterns)}


@app.patch("/patterns/{pattern_id}")
async def update_pattern(pattern_id: str, update: PatternUpdate):
    """Update a pattern's status or notes."""
    db = get_database()
    try:
        pattern = await db.update_pattern_status(
            UUID(pattern_id),
            status=update.status,
            notes=update.notes
        )
        return pattern.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Opportunities endpoints
@app.get("/opportunities")
async def get_opportunities(
    status: Optional[str] = None,
    timing_stage: Optional[str] = None
):
    """Get opportunities with optional filters."""
    db = get_database()
    opportunities = await db.get_opportunities(
        status=status,
        timing_stage=timing_stage
    )
    return {"opportunities": [o.model_dump() for o in opportunities], "count": len(opportunities)}


@app.get("/opportunities/{opportunity_id}")
async def get_opportunity(opportunity_id: str):
    """Get a single opportunity by ID."""
    db = get_database()
    try:
        opportunities = await db.get_opportunities()
        for opp in opportunities:
            if str(opp.id) == opportunity_id:
                return opp.model_dump()
        raise HTTPException(status_code=404, detail="Opportunity not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.patch("/opportunities/{opportunity_id}")
async def update_opportunity(opportunity_id: str, update: OpportunityUpdate):
    """Update an opportunity's status or notes."""
    db = get_database()
    try:
        opportunity = await db.update_opportunity_status(
            UUID(opportunity_id),
            status=update.status,
            notes=update.notes
        )
        return opportunity.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Chat endpoints
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a chat message and get a response."""
    chat_interface = get_chat_interface()

    if request.conversation_id:
        conversation_id = UUID(request.conversation_id)
    else:
        conversation = await chat_interface.start_conversation()
        conversation_id = conversation.id

    response = await chat_interface.send_message(conversation_id, request.message)

    return ChatResponse(
        response=response,
        conversation_id=str(conversation_id)
    )


@app.post("/chat/opportunity/{opportunity_id}")
async def chat_about_opportunity(opportunity_id: str, request: ChatRequest):
    """Ask a question about a specific opportunity."""
    chat_interface = get_chat_interface()
    response = await chat_interface.ask_about_opportunity(
        UUID(opportunity_id),
        request.message
    )
    return {"response": response}


@app.post("/chat/thesis/{thesis_element}")
async def explore_thesis(thesis_element: str):
    """Explore signals related to a thesis element."""
    chat_interface = get_chat_interface()
    response = await chat_interface.explore_thesis(thesis_element)
    return {"response": response}


# Digest endpoints
@app.get("/digest/weekly")
async def get_weekly_digest():
    """Generate and return the weekly digest."""
    generator = get_digest_generator()
    digest = await generator.generate_weekly_digest()
    return digest.model_dump()


@app.get("/digest/monthly")
async def get_monthly_digest():
    """Generate and return the monthly digest."""
    generator = get_digest_generator()
    digest = await generator.generate_monthly_digest()
    return digest.model_dump()


# Alerts endpoints
@app.get("/alerts")
async def get_alerts():
    """Get pending alerts."""
    alert_system = get_alert_system()
    alerts = alert_system.get_pending_alerts()
    return {
        "alerts": [alert_system.format_alert_notification(a) for a in alerts],
        "count": len(alerts)
    }


@app.post("/alerts/check")
async def check_alerts():
    """Run anomaly detection and return new alerts."""
    alert_system = get_alert_system()
    alerts = await alert_system.check_for_anomalies()
    return {
        "new_alerts": [alert_system.format_alert_notification(a) for a in alerts],
        "count": len(alerts)
    }


@app.delete("/alerts/{alert_id}")
async def dismiss_alert(alert_id: str):
    """Dismiss an alert."""
    alert_system = get_alert_system()
    dismissed = alert_system.dismiss_alert(alert_id)
    return {"dismissed": dismissed}


# Pipeline endpoints
@app.post("/pipeline/collect")
async def run_collection(source: Optional[str] = None):
    """Run data collection."""
    register_all_collectors()

    if source:
        collector = registry.get(source)
        if not collector:
            raise HTTPException(status_code=404, detail=f"Collector '{source}' not found")
        count = await collector.run()
        return {"source": source, "signals_collected": count}
    else:
        results = await registry.run_all()
        return {"results": results}


@app.post("/pipeline/process")
async def run_processing(limit: int = Query(default=100, ge=1, le=1000)):
    """Process unprocessed signals."""
    pipeline = get_pipeline()
    count = await pipeline.process_unprocessed(limit=limit)
    return {"signals_processed": count}


@app.post("/pipeline/detect-patterns")
async def run_pattern_detection(days: int = Query(default=30, ge=1, le=90)):
    """Run pattern detection."""
    detector = get_pattern_detector()
    patterns = await detector.detect_all(days=days)
    return {"patterns_detected": len(patterns)}


@app.post("/pipeline/generate-opportunities")
async def run_opportunity_generation(min_score: float = Query(default=0.5, ge=0, le=1)):
    """Generate opportunities from patterns."""
    db = get_database()
    generator = get_opportunity_generator()

    patterns = await db.get_patterns(status="new", min_score=min_score)
    signals = await db.get_processed_signals(days=30)

    opportunities = await generator.generate_from_patterns(patterns, signals, min_score)
    return {"opportunities_generated": len(opportunities)}


@app.post("/pipeline/full")
async def run_full_pipeline():
    """Run the complete pipeline: collect, process, detect patterns, generate opportunities."""
    results = {}

    # Collect
    register_all_collectors()
    collection_results = await registry.run_all()
    results["collection"] = collection_results

    # Process
    pipeline = get_pipeline()
    processed = await pipeline.process_unprocessed(limit=500)
    results["processed"] = processed

    # Detect patterns
    detector = get_pattern_detector()
    patterns = await detector.detect_all(days=30)
    results["patterns_detected"] = len(patterns)

    # Generate opportunities
    db = get_database()
    generator = get_opportunity_generator()
    new_patterns = await db.get_patterns(status="new", min_score=0.5)
    signals = await db.get_processed_signals(days=30)
    opportunities = await generator.generate_from_patterns(new_patterns, signals)
    results["opportunities_generated"] = len(opportunities)

    return results


# Stats endpoint
@app.get("/stats")
async def get_stats():
    """Get system statistics."""
    db = get_database()

    signals = await db.get_processed_signals(days=30)
    patterns = await db.get_patterns()
    opportunities = await db.get_opportunities()

    # Calculate thesis distribution
    thesis_counts = {
        "ai_leverage": 0,
        "trust_scarcity": 0,
        "physical_digital": 0,
        "incumbent_decay": 0,
        "speed_advantage": 0,
        "execution_fit": 0
    }

    for s in signals:
        if s.thesis_scores:
            if s.thesis_scores.ai_leverage and s.thesis_scores.ai_leverage >= 7:
                thesis_counts["ai_leverage"] += 1
            if s.thesis_scores.trust_scarcity and s.thesis_scores.trust_scarcity >= 7:
                thesis_counts["trust_scarcity"] += 1
            if s.thesis_scores.physical_digital and s.thesis_scores.physical_digital >= 7:
                thesis_counts["physical_digital"] += 1
            if s.thesis_scores.incumbent_decay and s.thesis_scores.incumbent_decay >= 7:
                thesis_counts["incumbent_decay"] += 1
            if s.thesis_scores.speed_advantage and s.thesis_scores.speed_advantage >= 7:
                thesis_counts["speed_advantage"] += 1
            if s.thesis_scores.execution_fit and s.thesis_scores.execution_fit >= 7:
                thesis_counts["execution_fit"] += 1

    return {
        "signals_30d": len(signals),
        "patterns_total": len(patterns),
        "patterns_new": len([p for p in patterns if p.status == PatternStatus.NEW]),
        "opportunities_total": len(opportunities),
        "opportunities_new": len([o for o in opportunities if o.status == OpportunityStatus.NEW]),
        "thesis_distribution": thesis_counts
    }
