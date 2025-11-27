"""Reddit collector using PRAW."""

from datetime import datetime
from typing import List, Optional
import asyncio

import praw
from praw.models import Submission

from .base import BaseCollector, CollectorConfig
from ..database import RawSignalCreate
from ..utils import get_logger, get_settings, TARGET_SUBREDDITS

logger = get_logger(__name__)


class RedditCollector(BaseCollector):
    """Collector for Reddit posts and trends."""

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
        """Collect top posts from target subreddits."""
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
                    signals.append(self.create_signal(
                        raw_content={
                            "type": "subreddit_top_posts",
                            "subreddit": subreddit_name,
                            "posts": posts
                        },
                        source_url=f"https://reddit.com/r/{subreddit_name}",
                        geography="global"
                    ))

            except Exception as e:
                logger.error(f"Error collecting from r/{subreddit_name}", error=str(e))
                continue

        return signals

    def _get_subreddit_posts(self, subreddit_name: str) -> Optional[List[dict]]:
        """Get top posts from a subreddit."""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []

            # Get top posts from past week
            for submission in subreddit.top(time_filter="week", limit=25):
                posts.append(self._submission_to_dict(submission))

            # Also get hot posts
            for submission in subreddit.hot(limit=15):
                post_dict = self._submission_to_dict(submission)
                if post_dict not in posts:
                    posts.append(post_dict)

            return posts if posts else None

        except Exception as e:
            logger.warning(f"Failed to get posts from r/{subreddit_name}", error=str(e))
            return None

    def _submission_to_dict(self, submission: Submission) -> dict:
        """Convert a Reddit submission to a dictionary."""
        return {
            "id": submission.id,
            "title": submission.title,
            "selftext": submission.selftext[:1000] if submission.selftext else "",
            "score": submission.score,
            "upvote_ratio": submission.upvote_ratio,
            "num_comments": submission.num_comments,
            "created_utc": submission.created_utc,
            "url": f"https://reddit.com{submission.permalink}",
            "link_url": submission.url if not submission.is_self else None,
            "flair": submission.link_flair_text
        }
