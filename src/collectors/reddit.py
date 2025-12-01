"""Reddit collector using PRAW - Solo SaaS Finder v2.0"""

from datetime import datetime
from typing import List, Optional
import asyncio
import re

import praw
from praw.models import Submission

from .base import BaseCollector, CollectorConfig
from ..database import RawSignalCreate
from ..utils import get_logger, get_settings, TARGET_SUBREDDITS, DEMAND_SIGNAL_PATTERNS

logger = get_logger(__name__)


class RedditCollector(BaseCollector):
    """
    Collector for Reddit posts and trends focused on SaaS opportunities.

    Monitors subreddits for:
    - Business problems and pain points
    - Requests for software solutions
    - Complaints about existing tools
    - Industry-specific challenges
    """

    def __init__(self):
        config = CollectorConfig(
            name="reddit",
            source_type="reddit",
            source_category="mass_behaviour",
            rate_limiter_key="reddit"
        )
        super().__init__(config)

        settings = get_settings()
        self.reddit = None
        if settings.reddit_client_id and settings.reddit_client_secret:
            self.reddit = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent
            )

    async def collect(self) -> List[RawSignalCreate]:
        """Collect top posts from target subreddits focused on finding SaaS opportunities."""
        if not self.reddit:
            logger.warning("Reddit credentials not configured, skipping collection")
            return []

        signals = []
        loop = asyncio.get_event_loop()

        for subreddit_name in TARGET_SUBREDDITS:
            try:
                await self.rate_limiter.acquire()

                posts = await loop.run_in_executor(
                    None,
                    lambda: self._get_subreddit_posts(subreddit_name)
                )

                if posts:
                    # Separate high-value demand signals from regular posts
                    demand_posts = [p for p in posts if p.get("is_demand_signal")]
                    regular_posts = [p for p in posts if not p.get("is_demand_signal")]

                    # Create signal for demand signals (higher priority)
                    if demand_posts:
                        signals.append(self.create_signal(
                            raw_content={
                                "type": "demand_signals",
                                "subreddit": subreddit_name,
                                "posts": demand_posts,
                                "signal_priority": "high"
                            },
                            source_url=f"https://reddit.com/r/{subreddit_name}",
                            geography="global"
                        ))

                    # Create signal for regular posts
                    if regular_posts:
                        signals.append(self.create_signal(
                            raw_content={
                                "type": "subreddit_posts",
                                "subreddit": subreddit_name,
                                "posts": regular_posts,
                                "signal_priority": "normal"
                            },
                            source_url=f"https://reddit.com/r/{subreddit_name}",
                            geography="global"
                        ))

            except Exception as e:
                logger.error(f"Error collecting from r/{subreddit_name}", error=str(e))
                continue

        return signals

    def _get_subreddit_posts(self, subreddit_name: str) -> Optional[List[dict]]:
        """Get posts from a subreddit with demand signal detection."""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []
            seen_ids = set()

            # Get top posts from past week
            for submission in subreddit.top(time_filter="week", limit=25):
                if submission.id not in seen_ids:
                    posts.append(self._submission_to_dict(submission))
                    seen_ids.add(submission.id)

            # Get hot posts
            for submission in subreddit.hot(limit=15):
                if submission.id not in seen_ids:
                    posts.append(self._submission_to_dict(submission))
                    seen_ids.add(submission.id)

            # Search for demand signal patterns
            for pattern in DEMAND_SIGNAL_PATTERNS[:5]:  # Limit patterns to avoid rate limits
                try:
                    for submission in subreddit.search(pattern, time_filter="week", limit=10):
                        if submission.id not in seen_ids:
                            post_dict = self._submission_to_dict(submission)
                            post_dict["matched_demand_pattern"] = pattern
                            posts.append(post_dict)
                            seen_ids.add(submission.id)
                except Exception as e:
                    logger.debug(f"Search pattern '{pattern}' failed in r/{subreddit_name}: {e}")
                    continue

            return posts if posts else None

        except Exception as e:
            logger.warning(f"Failed to get posts from r/{subreddit_name}", error=str(e))
            return None

    def _submission_to_dict(self, submission: Submission) -> dict:
        """Convert a Reddit submission to a dictionary with demand signal detection."""
        title_lower = submission.title.lower()
        selftext_lower = (submission.selftext or "").lower()
        combined_text = f"{title_lower} {selftext_lower}"

        # Check for demand signal patterns
        is_demand_signal = False
        matched_patterns = []

        for pattern in DEMAND_SIGNAL_PATTERNS:
            if pattern.lower() in combined_text:
                is_demand_signal = True
                matched_patterns.append(pattern)

        # Additional demand signal indicators
        demand_keywords = [
            "recommend", "suggestion", "alternative", "better than",
            "hate", "frustrating", "annoying", "broken", "doesn't work",
            "expensive", "overpriced", "looking for", "need a",
            "any software", "any tool", "any app"
        ]

        for keyword in demand_keywords:
            if keyword in combined_text and keyword not in matched_patterns:
                if not is_demand_signal:
                    matched_patterns.append(keyword)
                is_demand_signal = True

        return {
            "id": submission.id,
            "title": submission.title,
            "selftext": submission.selftext[:2000] if submission.selftext else "",
            "score": submission.score,
            "upvote_ratio": submission.upvote_ratio,
            "num_comments": submission.num_comments,
            "created_utc": submission.created_utc,
            "url": f"https://reddit.com{submission.permalink}",
            "link_url": submission.url if not submission.is_self else None,
            "flair": submission.link_flair_text,
            "is_demand_signal": is_demand_signal,
            "matched_patterns": matched_patterns,
            "subreddit": submission.subreddit.display_name
        }


class RedditDemandSearchCollector(BaseCollector):
    """
    Specialized collector that searches Reddit for demand signals.

    Uses targeted search queries to find posts where people are:
    - Asking for tool recommendations
    - Complaining about existing solutions
    - Describing manual processes they want to automate
    """

    def __init__(self):
        config = CollectorConfig(
            name="reddit_demand_search",
            source_type="reddit",
            source_category="demand_signals",
            rate_limiter_key="reddit"
        )
        super().__init__(config)

        settings = get_settings()
        self.reddit = None
        if settings.reddit_client_id and settings.reddit_client_secret:
            self.reddit = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent
            )

    async def collect(self) -> List[RawSignalCreate]:
        """Search across Reddit for demand signals."""
        if not self.reddit:
            logger.warning("Reddit credentials not configured, skipping demand search")
            return []

        signals = []
        loop = asyncio.get_event_loop()

        # High-value search queries for finding SaaS opportunities
        search_queries = [
            # Tool requests
            '"is there a tool" OR "is there software"',
            '"looking for a solution" OR "looking for software"',
            '"any recommendations for" software OR tool',
            '"does anyone know" tool OR software OR app',

            # Pain points
            '"spreadsheet hell" OR "excel nightmare"',
            '"manual process" OR "waste so much time"',
            '"frustrated with" software OR tool',
            '"hate" software tool -"hate speech"',

            # Automation desires
            '"wish there was" software OR tool OR app',
            '"automate" repetitive OR manual',
            '"better alternative to"',

            # Business-specific
            '"small business" software need OR looking',
            'CRM alternative small business',
            'scheduling software freelancer OR contractor',
        ]

        for query in search_queries:
            try:
                await self.rate_limiter.acquire()

                posts = await loop.run_in_executor(
                    None,
                    lambda q=query: self._search_reddit(q)
                )

                if posts:
                    signals.append(self.create_signal(
                        raw_content={
                            "type": "demand_search",
                            "search_query": query,
                            "posts": posts
                        },
                        source_url=f"https://reddit.com/search?q={query}",
                        geography="global"
                    ))

            except Exception as e:
                logger.error(f"Error searching Reddit for '{query}'", error=str(e))
                continue

        return signals

    def _search_reddit(self, query: str) -> Optional[List[dict]]:
        """Search Reddit with a specific query."""
        try:
            posts = []
            seen_ids = set()

            for submission in self.reddit.subreddit("all").search(
                query,
                time_filter="month",
                limit=25,
                sort="relevance"
            ):
                if submission.id not in seen_ids:
                    # Skip posts from disqualified subreddits
                    skip_subreddits = [
                        "legaladvice", "personalfinance", "investing",
                        "healthit", "medicine", "insurance", "gambling"
                    ]
                    if submission.subreddit.display_name.lower() in skip_subreddits:
                        continue

                    posts.append({
                        "id": submission.id,
                        "title": submission.title,
                        "selftext": submission.selftext[:2000] if submission.selftext else "",
                        "score": submission.score,
                        "upvote_ratio": submission.upvote_ratio,
                        "num_comments": submission.num_comments,
                        "created_utc": submission.created_utc,
                        "url": f"https://reddit.com{submission.permalink}",
                        "subreddit": submission.subreddit.display_name,
                        "flair": submission.link_flair_text,
                        "search_query": query
                    })
                    seen_ids.add(submission.id)

            return posts if posts else None

        except Exception as e:
            logger.warning(f"Reddit search failed for query: {query}", error=str(e))
            return None
