"""GitHub trending collector."""

from datetime import datetime
from typing import List, Optional
import asyncio

import httpx
from bs4 import BeautifulSoup

from .base import BaseCollector, CollectorConfig
from ..database import RawSignalCreate
from ..utils import get_logger, get_settings

logger = get_logger(__name__)

# Languages to track
LANGUAGES = [
    "",  # All languages
    "python",
    "javascript",
    "typescript",
    "rust",
    "go"
]

# Time ranges
TIME_RANGES = ["daily", "weekly", "monthly"]


class GitHubTrendingCollector(BaseCollector):
    """Collector for GitHub trending repositories."""

    def __init__(self):
        config = CollectorConfig(
            name="github_trending",
            source_type="github",
            source_category="builder",
            rate_limiter_key="github"
        )
        super().__init__(config)
        settings = get_settings()
        self.headers = {}
        if settings.github_token:
            self.headers["Authorization"] = f"token {settings.github_token}"

    async def collect(self) -> List[RawSignalCreate]:
        """Collect trending repositories."""
        signals = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for language in LANGUAGES:
                for time_range in TIME_RANGES:
                    try:
                        await self.rate_limiter.acquire()

                        repos = await self._get_trending_repos(
                            client, language, time_range
                        )

                        if repos:
                            signals.append(self.create_signal(
                                raw_content={
                                    "type": "trending_repos",
                                    "language": language or "all",
                                    "time_range": time_range,
                                    "repositories": repos
                                },
                                source_url=f"https://github.com/trending/{language}?since={time_range}",
                                geography="global"
                            ))

                    except Exception as e:
                        logger.error(
                            f"Error collecting GitHub trends",
                            language=language,
                            time_range=time_range,
                            error=str(e)
                        )
                        continue

        return signals

    async def _get_trending_repos(
        self,
        client: httpx.AsyncClient,
        language: str,
        time_range: str
    ) -> Optional[List[dict]]:
        """Scrape trending repos from GitHub."""
        try:
            url = f"https://github.com/trending/{language}"
            params = {"since": time_range}

            response = await client.get(url, params=params, headers=self.headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            repos = []

            for article in soup.select('article.Box-row'):
                try:
                    # Repository name and link
                    name_elem = article.select_one('h2 a')
                    if not name_elem:
                        continue

                    repo_name = name_elem.text.strip().replace('\n', '').replace(' ', '')
                    repo_url = f"https://github.com{name_elem['href']}"

                    # Description
                    desc_elem = article.select_one('p')
                    description = desc_elem.text.strip() if desc_elem else ""

                    # Language
                    lang_elem = article.select_one('[itemprop="programmingLanguage"]')
                    prog_language = lang_elem.text.strip() if lang_elem else ""

                    # Stars
                    stars_elem = article.select_one('a[href$="/stargazers"]')
                    stars = stars_elem.text.strip().replace(',', '') if stars_elem else "0"

                    # Stars today/this week
                    stars_today_elem = article.select_one('span.d-inline-block.float-sm-right')
                    stars_today = ""
                    if stars_today_elem:
                        stars_today = stars_today_elem.text.strip()

                    repos.append({
                        "name": repo_name,
                        "url": repo_url,
                        "description": description,
                        "language": prog_language,
                        "stars": stars,
                        "stars_period": stars_today
                    })

                except Exception as e:
                    logger.warning(f"Error parsing repo", error=str(e))
                    continue

            return repos[:25] if repos else None

        except Exception as e:
            logger.warning(f"Failed to scrape GitHub trending", error=str(e))
            return None
