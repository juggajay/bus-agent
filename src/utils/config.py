"""Configuration management for Opportunity Intelligence Agent."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
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


# Thesis configuration - hardcoded as per spec
THESIS = {
    "ai_leverage": {
        "name": "AI Leverage",
        "description": "Does this opportunity allow a solo operator or small team to do what previously required 20+ people? Is AI a genuine force multiplier here or just a feature?",
        "weight": 1.0
    },
    "trust_scarcity": {
        "name": "Trust Scarcity",
        "description": "In a world where everything can be faked, does this opportunity leverage verified credentials, provable data, or authentic expertise as a moat?",
        "weight": 1.0
    },
    "physical_digital": {
        "name": "Physical-Digital Intersection",
        "description": "Is this where atoms meet bits? The underexplored space where real-world friction meets software solutions.",
        "weight": 1.0
    },
    "incumbent_decay": {
        "name": "Incumbent Decay",
        "description": "Are existing players slow, bloated, protected by inertia, or failing to adapt? Is there a window to move fast?",
        "weight": 1.0
    },
    "speed_advantage": {
        "name": "Speed Advantage",
        "description": "Can this be executed quickly? Is first-to-iterate-well still a viable strategy here?",
        "weight": 1.0
    },
    "execution_fit": {
        "name": "Execution Edge Fit",
        "description": "How well does this match the operator's specific strengths (construction/trades knowledge, technical ability, solo operator model, Australia/SEA geography)?",
        "weight": 1.2  # Slightly higher weight for personal fit
    }
}

# Operator profile - hardcoded as per spec
OPERATOR_PROFILE = {
    "background": "Solo entrepreneur with construction/carpentry background",
    "technical_ability": "Can build software",
    "geography": "Based in Australia with knowledge of SEA markets",
    "preferences": [
        "Opportunities with data moats",
        "Regulatory advantages",
        "Quick execution",
        "Minimal team or capital requirements"
    ],
    "strengths": [
        "Construction/trades domain knowledge",
        "Technical implementation ability",
        "Solo operator efficiency",
        "Australia/SEA market understanding"
    ]
}

# Target subreddits for monitoring
TARGET_SUBREDDITS = [
    # Business/Entrepreneurship
    "smallbusiness", "entrepreneur", "startups",
    # Australian markets
    "australia", "ausfinance", "australianpolitics",
    # Construction/Trades
    "construction", "contractors", "trades",
    "plumbing", "electricians", "HVAC", "pestcontrol",
    # Tech/SaaS
    "SaaS", "webdev", "programming",
    # Real estate
    "realestate", "landlords",
    # AI/ML
    "LocalLLaMA", "MachineLearning", "artificial"
]

# Signal types for classification
SIGNAL_TYPES = {
    "trend": ["rising", "declining", "stable", "breakout"],
    "complaint": ["product", "service", "pricing", "availability"],
    "regulatory": ["new_requirement", "deregulation", "enforcement", "proposed"],
    "funding": ["seed", "series_a", "series_b_plus", "acquisition", "ipo"],
    "job_market": ["new_role", "hiring_surge", "layoffs", "skill_shift"],
    "builder_activity": ["new_project", "trending_repo", "package_growth", "launch"],
    "consumer_behaviour": ["spending_shift", "platform_migration", "search_intent"],
    "competitive": ["new_entrant", "incumbent_move", "market_exit", "pricing_change"]
}

# Geography codes
GEOGRAPHIES = ["US", "UK", "AU", "CA", "NZ", "global"]

# Timing stages
TIMING_STAGES = ["early", "emerging", "growing", "crowded"]


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
