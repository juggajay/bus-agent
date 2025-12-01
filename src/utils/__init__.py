"""Utility modules - Solo SaaS Finder v2.0"""

from .config import (
    get_settings,
    Settings,
    THESIS,
    OPERATOR_PROFILE,
    TARGET_SUBREDDITS,
    SIGNAL_TYPES,
    DISQUALIFIED_INDUSTRIES,
    DEMAND_SIGNAL_PATTERNS,
    OPPORTUNITY_TYPES,
    OPPORTUNITY_VERDICTS,
    GEOGRAPHIES,
    TIMING_STAGES,
    is_disqualified_industry
)
from .logging import setup_logging, get_logger
from .rate_limiting import RateLimiter, get_rate_limiter, with_retry

__all__ = [
    # Settings
    "get_settings",
    "Settings",
    # Thesis and config
    "THESIS",
    "OPERATOR_PROFILE",
    "TARGET_SUBREDDITS",
    "SIGNAL_TYPES",
    "DISQUALIFIED_INDUSTRIES",
    "DEMAND_SIGNAL_PATTERNS",
    "OPPORTUNITY_TYPES",
    "OPPORTUNITY_VERDICTS",
    "GEOGRAPHIES",
    "TIMING_STAGES",
    "is_disqualified_industry",
    # Logging
    "setup_logging",
    "get_logger",
    # Rate limiting
    "RateLimiter",
    "get_rate_limiter",
    "with_retry"
]
