"""Configuration management for Opportunity Intelligence Agent."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_key: str = Field(..., env="SUPABASE_KEY")
    supabase_service_key: Optional[str] = Field(None, env="SUPABASE_SERVICE_KEY")
    database_url: str = Field(..., env="DATABASE_URL")

    # LLM APIs
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")

    # Data source APIs
    reddit_client_id: Optional[str] = Field(None, env="REDDIT_CLIENT_ID")
    reddit_client_secret: Optional[str] = Field(None, env="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field("opportunity-intel/1.0", env="REDDIT_USER_AGENT")
    github_token: Optional[str] = Field(None, env="GITHUB_TOKEN")
    youtube_api_key: Optional[str] = Field(None, env="YOUTUBE_API_KEY")
    crunchbase_api_key: Optional[str] = Field(None, env="CRUNCHBASE_API_KEY")

    # Notifications
    smtp_host: Optional[str] = Field(None, env="SMTP_HOST")
    smtp_port: int = Field(587, env="SMTP_PORT")
    smtp_user: Optional[str] = Field(None, env="SMTP_USER")
    smtp_password: Optional[str] = Field(None, env="SMTP_PASSWORD")
    notification_email: Optional[str] = Field(None, env="NOTIFICATION_EMAIL")

    # Config
    environment: str = Field("development", env="ENVIRONMENT")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    timezone: str = Field("Australia/Sydney", env="TIMEZONE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# New thesis configuration - Solo SaaS Finder v2.0
THESIS = {
    "demand_evidence": {
        "name": "Demand Evidence",
        "description": "Proof people want this and would pay. Are people actively searching? Complaints in forums? Asking 'is there a tool for X'?",
        "weight": 1.0
    },
    "competition_gap": {
        "name": "Competition Gap",
        "description": "Is the space empty or poorly served? Outdated, overpriced, or poorly executed players?",
        "weight": 1.0
    },
    "trend_timing": {
        "name": "Trend Timing",
        "description": "Is this the right time? Emerging trend, growing search volume, early adopters looking?",
        "weight": 0.8
    },
    "solo_buildability": {
        "name": "Solo Buildability",
        "description": "Can one person build an MVP in 2-4 weeks? Straightforward technical requirements?",
        "weight": 1.0
    },
    "clear_monetisation": {
        "name": "Clear Monetisation",
        "description": "Will people pay monthly? Obvious subscription or listing fee model?",
        "weight": 1.0
    },
    "regulatory_simplicity": {
        "name": "Regulatory Simplicity",
        "description": "Is it regulation-free? No licensing, compliance, or legal complexity?",
        "weight": 1.0
    }
}

# Operator profile - Solo SaaS builder
OPERATOR_PROFILE = {
    "team_size": 1,
    "funding": "none",
    "technical_skills": "full_stack",
    "time_to_mvp": "2-4 weeks",
    "preferences": [
        "Fast to ship",
        "Clear monetisation",
        "Subscription or listing revenue",
        "Avoid regulated industries",
        "Solo buildable"
    ],
    "strengths": [
        "Full-stack development",
        "Fast iteration",
        "Solo execution"
    ]
}

# Industries to automatically disqualify
DISQUALIFIED_INDUSTRIES = [
    # Financial services
    "financial services", "fintech", "banking", "lending", "payments",
    "investing", "cryptocurrency", "trading",
    # Healthcare
    "healthcare", "healthtech", "medical", "telehealth", "patient data",
    "medical devices",
    # Legal
    "legal", "legal tech", "law", "legal advice",
    # Insurance
    "insurance", "insurtech",
    # Gambling
    "gambling", "betting", "casino", "sports betting",
    # Other regulated
    "pharmaceuticals", "cannabis", "marijuana", "firearms", "weapons",
    "government contracting", "controlled substances"
]

# Target subreddits for monitoring - focused on finding business problems
TARGET_SUBREDDITS = [
    # Business/Entrepreneur - where people discuss problems
    "smallbusiness", "entrepreneur", "sweatystartup",
    "SaaS", "microsaas", "indiehackers",

    # Industry-specific (problems, not solutions)
    "realestate", "realestateinvesting",
    "ecommerce", "dropshipping",
    "agencies", "marketing", "SEO", "PPC",
    "photography", "videography", "wedding",
    "fitness",  # gym owners
    "restaurateur", "barowners", "hoteliers",
    "airbnb_hosts", "landlords", "propertymanagement",

    # Trades (non-regulated)
    "landscaping", "lawncare", "pressurewashing",
    "autodetailing", "carwash", "cleaning",
    "homeimprovement", "HVAC", "pestcontrol",
    "roofing", "electricians", "plumbing",
    "contractors"
]

# Search patterns for finding demand signals in Reddit
DEMAND_SIGNAL_PATTERNS = [
    "is there a tool",
    "is there software",
    "I wish there was",
    "does anyone know a",
    "looking for a solution",
    "spreadsheet hell",
    "manual process",
    "waste so much time",
    "anyone know of",
    "recommendation for",
    "what do you use for",
    "how do you handle",
    "struggling with",
    "pain point",
    "frustrated with"
]

# Signal types for classification - updated for SaaS focus
SIGNAL_TYPES = {
    "demand_signal": ["active_search", "feature_request", "willing_to_pay", "asking_for_tool"],
    "complaint": ["existing_tool", "pricing", "missing_feature", "poor_ux", "reliability"],
    "trend": ["rising", "emerging", "growing", "stable"],
    "competition_intel": ["new_player", "weakness", "pricing_change", "shutdown", "pivot"],
    "market_shift": ["industry_change", "regulation_change", "technology_shift", "behavior_change"],
    "builder_activity": ["new_launch", "trending_repo", "indie_success", "saas_launch"]
}

# Opportunity types prioritization
OPPORTUNITY_TYPES = {
    "tier_1": ["vertical_saas", "directory", "micro_saas", "productised_service"],
    "tier_2": ["internal_tools", "workflow_automation", "data_product"],
    "tier_3": ["marketplace", "platform"]
}

# Verdict options for opportunities
OPPORTUNITY_VERDICTS = ["BUILD NOW", "EXPLORE", "MONITOR", "PASS"]

# Geography codes
GEOGRAPHIES = ["US", "UK", "AU", "CA", "NZ", "global"]

# Timing stages
TIMING_STAGES = ["early", "emerging", "growing", "crowded"]


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()


def is_disqualified_industry(industry: str) -> bool:
    """Check if an industry is in the disqualified list."""
    industry_lower = industry.lower()
    return any(
        disqualified.lower() in industry_lower or industry_lower in disqualified.lower()
        for disqualified in DISQUALIFIED_INDUSTRIES
    )
