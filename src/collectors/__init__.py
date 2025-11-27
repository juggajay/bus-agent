"""Data collectors module."""

from .base import BaseCollector, CollectorConfig, CollectorRegistry, registry
from .google_trends import GoogleTrendsCollector
from .github import GitHubTrendingCollector
from .reddit import RedditCollector
from .hacker_news import HackerNewsCollector
from .product_hunt import ProductHuntCollector


def register_all_collectors():
    """Register all available collectors."""
    registry.register(GoogleTrendsCollector())
    registry.register(GitHubTrendingCollector())
    registry.register(RedditCollector())
    registry.register(HackerNewsCollector())
    registry.register(ProductHuntCollector())


__all__ = [
    "BaseCollector",
    "CollectorConfig",
    "CollectorRegistry",
    "registry",
    "register_all_collectors",
    "GoogleTrendsCollector",
    "GitHubTrendingCollector",
    "RedditCollector",
    "HackerNewsCollector",
    "ProductHuntCollector"
]
