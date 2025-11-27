"""Rate limiting utilities for API calls."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass, field
from collections import deque
import time

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)


@dataclass
class RateLimiter:
    """Token bucket rate limiter for API calls."""

    requests_per_minute: int
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None

    _minute_window: deque = field(default_factory=deque)
    _hour_window: deque = field(default_factory=deque)
    _day_window: deque = field(default_factory=deque)

    def _clean_window(self, window: deque, seconds: int) -> None:
        """Remove timestamps older than the window."""
        cutoff = time.time() - seconds
        while window and window[0] < cutoff:
            window.popleft()

    async def acquire(self) -> None:
        """Wait until a request can be made within rate limits."""
        while True:
            now = time.time()

            # Clean windows
            self._clean_window(self._minute_window, 60)
            if self.requests_per_hour:
                self._clean_window(self._hour_window, 3600)
            if self.requests_per_day:
                self._clean_window(self._day_window, 86400)

            # Check limits
            minute_ok = len(self._minute_window) < self.requests_per_minute
            hour_ok = (self.requests_per_hour is None or
                      len(self._hour_window) < self.requests_per_hour)
            day_ok = (self.requests_per_day is None or
                     len(self._day_window) < self.requests_per_day)

            if minute_ok and hour_ok and day_ok:
                self._minute_window.append(now)
                if self.requests_per_hour:
                    self._hour_window.append(now)
                if self.requests_per_day:
                    self._day_window.append(now)
                return

            # Calculate wait time
            if not minute_ok:
                wait_time = 60 - (now - self._minute_window[0])
            elif not hour_ok:
                wait_time = 3600 - (now - self._hour_window[0])
            else:
                wait_time = 86400 - (now - self._day_window[0])

            await asyncio.sleep(min(wait_time + 0.1, 60))


# Pre-configured rate limiters for common APIs
RATE_LIMITERS: Dict[str, RateLimiter] = {
    "google_trends": RateLimiter(requests_per_minute=10, requests_per_hour=100),
    "github": RateLimiter(requests_per_minute=30, requests_per_hour=5000),
    "reddit": RateLimiter(requests_per_minute=60),
    "youtube": RateLimiter(requests_per_minute=100, requests_per_day=10000),
    "anthropic": RateLimiter(requests_per_minute=50),
    "openai": RateLimiter(requests_per_minute=60),
    "hacker_news": RateLimiter(requests_per_minute=30),
    "product_hunt": RateLimiter(requests_per_minute=20),
    "default": RateLimiter(requests_per_minute=30)
}


def get_rate_limiter(source: str) -> RateLimiter:
    """Get the rate limiter for a specific source."""
    return RATE_LIMITERS.get(source, RATE_LIMITERS["default"])


# Retry decorator with exponential backoff
def with_retry(max_attempts: int = 3, min_wait: int = 1, max_wait: int = 60):
    """Decorator for retrying failed operations with exponential backoff."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
