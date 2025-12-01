"""FastAPI web interface - Solo SaaS Finder v2.0"""

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
    title="Solo SaaS Finder",
    description="Automated SaaS and directory business opportunity discovery system",
    version="2.0.0"
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
    return {
        "status": "healthy",
        "version": "2.0.0",
        "name": "Solo SaaS Finder",
        "timestamp": datetime.utcnow().isoformat()
    }


# Signals endpoints
@app.get("/signals")
async def get_signals(
    days: int = Query(default=7, ge=1, le=90),
    signal_type: Optional[str] = None,
    min_thesis_score: Optional[int] = Query(default=None, ge=1, le=10),
    exclude_disqualified: bool = Query(default=True)
):
    """Get processed signals with optional filters."""
    db = get_database()
    signals = await db.get_processed_signals(
        days=days,
        signal_type=signal_type,
        min_thesis_score=min_thesis_score
    )

    # Filter out disqualified signals if requested
    if exclude_disqualified:
        signals = [s for s in signals if not getattr(s, 'is_disqualified', False)]

    return {"signals": [s.model_dump() for s in signals], "count": len(signals)}


@app.get("/signals/demand")
async def get_demand_signals(
    days: int = Query(default=7, ge=1, le=90),
    min_demand_score: Optional[int] = Query(default=7, ge=1, le=10)
):
    """Get signals with high demand evidence scores."""
    db = get_database()
    signals = await db.get_processed_signals(days=days)

    # Filter for demand signals with high scores
    demand_signals = [
        s for s in signals
        if not getattr(s, 'is_disqualified', False)
        and s.thesis_scores
        and getattr(s.thesis_scores, 'demand_evidence', 0) >= min_demand_score
    ]

    return {"signals": [s.model_dump() for s in demand_signals], "count": len(demand_signals)}


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
    timing_stage: Optional[str] = None,
    verdict: Optional[str] = None,
    opportunity_type: Optional[str] = None
):
    """Get opportunities with optional filters."""
    db = get_database()
    opportunities = await db.get_opportunities(
        status=status,
        timing_stage=timing_stage
    )

    # Additional filtering
    if verdict:
        opportunities = [o for o in opportunities if getattr(o, 'verdict', None) == verdict]
    if opportunity_type:
        opportunities = [o for o in opportunities if o.opportunity_type == opportunity_type]

    return {"opportunities": [o.model_dump() for o in opportunities], "count": len(opportunities)}


@app.get("/opportunities/build-now")
async def get_build_now_opportunities():
    """Get all opportunities with BUILD NOW verdict."""
    db = get_database()
    opportunities = await db.get_opportunities()
    build_now = [o for o in opportunities if getattr(o, 'verdict', None) == "BUILD NOW"]
    return {"opportunities": [o.model_dump() for o in build_now], "count": len(build_now)}


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


@app.post("/chat/factor/{factor}")
async def explore_scoring_factor(factor: str):
    """Explore signals related to a scoring factor (Solo SaaS Finder v2.0)."""
    chat_interface = get_chat_interface()
    response = await chat_interface.explore_scoring_factor(factor)
    return {"response": response}


@app.get("/chat/recommendations")
async def get_build_recommendations():
    """Get recommendations for what to build based on current data."""
    chat_interface = get_chat_interface()
    response = await chat_interface.get_build_recommendations()
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


# Stats endpoint - Updated for Solo SaaS Finder v2.0
@app.get("/stats")
async def get_stats():
    """Get system statistics with new scoring factors."""
    db = get_database()

    signals = await db.get_processed_signals(days=30)
    patterns = await db.get_patterns()
    opportunities = await db.get_opportunities()

    # Filter out disqualified signals for stats
    valid_signals = [s for s in signals if not getattr(s, 'is_disqualified', False)]
    disqualified_count = len(signals) - len(valid_signals)

    # Calculate new thesis distribution (Solo SaaS Finder v2.0)
    thesis_counts = {
        "demand_evidence": 0,
        "competition_gap": 0,
        "trend_timing": 0,
        "solo_buildability": 0,
        "clear_monetisation": 0,
        "regulatory_simplicity": 0
    }

    thesis_averages = {
        "demand_evidence": [],
        "competition_gap": [],
        "trend_timing": [],
        "solo_buildability": [],
        "clear_monetisation": [],
        "regulatory_simplicity": []
    }

    for s in valid_signals:
        if s.thesis_scores:
            for key in thesis_counts:
                score = getattr(s.thesis_scores, key, None)
                if score:
                    thesis_averages[key].append(score)
                    if score >= 7:
                        thesis_counts[key] += 1

    # Calculate averages
    thesis_avg = {}
    for key, scores in thesis_averages.items():
        thesis_avg[key] = round(sum(scores) / len(scores), 2) if scores else 0

    # Count opportunities by verdict
    verdict_counts = {}
    for o in opportunities:
        verdict = getattr(o, 'verdict', None) or 'N/A'
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    # Count opportunities by type
    type_counts = {}
    for o in opportunities:
        otype = o.opportunity_type or 'unknown'
        type_counts[otype] = type_counts.get(otype, 0) + 1

    # Signal type distribution
    signal_type_counts = {}
    for s in valid_signals:
        stype = s.signal_type or 'unknown'
        signal_type_counts[stype] = signal_type_counts.get(stype, 0) + 1

    return {
        "version": "2.0.0",
        "name": "Solo SaaS Finder",
        "signals_30d": len(valid_signals),
        "signals_disqualified": disqualified_count,
        "patterns_total": len(patterns),
        "patterns_new": len([p for p in patterns if p.status == PatternStatus.NEW]),
        "opportunities_total": len(opportunities),
        "opportunities_new": len([o for o in opportunities if o.status == OpportunityStatus.NEW]),
        "opportunities_build_now": verdict_counts.get("BUILD NOW", 0),
        "thesis_high_score_counts": thesis_counts,
        "thesis_averages": thesis_avg,
        "verdict_distribution": verdict_counts,
        "opportunity_type_distribution": type_counts,
        "signal_type_distribution": signal_type_counts
    }


# New endpoint: Scoring factors info
@app.get("/scoring-factors")
async def get_scoring_factors():
    """Get information about the 6 scoring factors used in Solo SaaS Finder v2.0."""
    return {
        "version": "2.0.0",
        "factors": [
            {
                "key": "demand_evidence",
                "name": "Demand Evidence",
                "weight": 1.0,
                "description": "Proof people want this and would pay. Are people actively searching? Complaints in forums? Asking 'is there a tool for X'?"
            },
            {
                "key": "competition_gap",
                "name": "Competition Gap",
                "weight": 1.0,
                "description": "Is the space empty or poorly served? Outdated, overpriced, or poorly executed players?"
            },
            {
                "key": "trend_timing",
                "name": "Trend Timing",
                "weight": 0.8,
                "description": "Is this the right time? Emerging trend, growing search volume, early adopters looking?"
            },
            {
                "key": "solo_buildability",
                "name": "Solo Buildability",
                "weight": 1.0,
                "description": "Can one person build an MVP in 2-4 weeks? Straightforward technical requirements?"
            },
            {
                "key": "clear_monetisation",
                "name": "Clear Monetisation",
                "weight": 1.0,
                "description": "Will people pay monthly? Obvious subscription or listing fee model?"
            },
            {
                "key": "regulatory_simplicity",
                "name": "Regulatory Simplicity",
                "weight": 1.0,
                "description": "Is it regulation-free? No licensing, compliance, or legal complexity?"
            }
        ],
        "disqualified_industries": [
            "financial services", "fintech", "banking", "lending", "payments", "investing",
            "healthcare", "healthtech", "medical", "telehealth",
            "legal", "legal tech", "law",
            "insurance", "gambling", "betting",
            "pharmaceuticals", "cannabis", "firearms", "government contracting"
        ],
        "opportunity_types": {
            "tier_1": ["vertical_saas", "directory", "micro_saas", "productised_service"],
            "tier_2": ["internal_tools", "workflow_automation", "data_product"],
            "tier_3": ["marketplace", "platform"]
        },
        "verdicts": ["BUILD NOW", "EXPLORE", "MONITOR", "PASS"]
    }
