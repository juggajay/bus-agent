"""Hacker News collector."""

from datetime import datetime
from typing import List, Optional
import asyncio

import httpx

from .base import BaseCollector, CollectorConfig
from ..database import RawSignalCreate
from ..utils import get_logger

logger = get_logger(__name__)

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsCollector(BaseCollector):
    """Collector for Hacker News stories."""

    def __init__(self):
        config = CollectorConfig(
            name="hacker_news",
            source_type="hacker_news",
            source_category="builder",
            rate_limiter_key="hacker_news"
        )
        super().__init__(config)

    async def collect(self) -> List[RawSignalCreate]:
        """Collect top stories, Show HN, and Ask HN posts."""
        signals = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Top stories
            top_stories = await self._get_stories(client, "topstories", limit=50)
            if top_stories:
                signals.append(self.create_signal(
                    raw_content={
                        "type": "top_stories",
                        "stories": top_stories
                    },
                    source_url="https://news.ycombinator.com/",
                    geography="global"
                ))

            # Show HN
            show_stories = await self._get_stories(client, "showstories", limit=30)
            if show_stories:
                signals.append(self.create_signal(
                    raw_content={
                        "type": "show_hn",
                        "stories": show_stories
                    },
                    source_url="https://news.ycombinator.com/show",
                    geography="global"
                ))

            # Ask HN
            ask_stories = await self._get_stories(client, "askstories", limit=30)
            if ask_stories:
                signals.append(self.create_signal(
                    raw_content={
                        "type": "ask_hn",
                        "stories": ask_stories
                    },
                    source_url="https://news.ycombinator.com/ask",
                    geography="global"
                ))

            # Best stories
            best_stories = await self._get_stories(client, "beststories", limit=30)
            if best_stories:
                signals.append(self.create_signal(
                    raw_content={
                        "type": "best_stories",
                        "stories": best_stories
                    },
                    source_url="https://news.ycombinator.com/best",
                    geography="global"
                ))

        return signals

    async def _get_stories(
        self,
        client: httpx.AsyncClient,
        story_type: str,
        limit: int = 50
    ) -> Optional[List[dict]]:
        """Get stories of a specific type."""
        try:
            await self.rate_limiter.acquire()

            # Get story IDs
            response = await client.get(f"{HN_API_BASE}/{story_type}.json")
            response.raise_for_status()
            story_ids = response.json()[:limit]

            # Fetch story details in parallel
            stories = await asyncio.gather(*[
                self._get_story(client, story_id)
                for story_id in story_ids
            ])

            return [s for s in stories if s is not None]

        except Exception as e:
            logger.warning(f"Failed to get {story_type}", error=str(e))
            return None

    async def _get_story(
        self,
        client: httpx.AsyncClient,
        story_id: int
    ) -> Optional[dict]:
        """Get a single story by ID."""
        try:
            await self.rate_limiter.acquire()

            response = await client.get(f"{HN_API_BASE}/item/{story_id}.json")
            response.raise_for_status()
            data = response.json()

            if not data:
                return None

            return {
                "id": data.get("id"),
                "title": data.get("title", ""),
                "url": data.get("url", ""),
                "text": data.get("text", "")[:500] if data.get("text") else "",
                "score": data.get("score", 0),
                "by": data.get("by", ""),
                "time": data.get("time"),
                "descendants": data.get("descendants", 0),
                "type": data.get("type", "story"),
                "hn_url": f"https://news.ycombinator.com/item?id={story_id}"
            }

        except Exception as e:
            logger.debug(f"Failed to get story {story_id}", error=str(e))
            return None
