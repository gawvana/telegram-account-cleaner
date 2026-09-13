import time
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import HTTPException, Request, status

class SlidingWindowRateLimiter:
    """In-memory sliding-window rate limiter per user/IP."""

    def __init__(self, times: int = 5, seconds: int = 60, name: str = "default"):
        self.times = times
        self.seconds = seconds
        self.name = name
        self._records: Dict[str, List[float]] = defaultdict(list)

    def _cleanup_old(self, key: str, now: float) -> None:
        threshold = now - self.seconds
        self._records[key] = [t for t in self._records[key] if t > threshold]
        if not self._records[key]:
            del self._records[key]

    async def check(self, key: str) -> None:
        now = time.time()
        self._cleanup_old(key, now)

        history = self._records[key]
        if len(history) >= self.times:
            retry_after = int(self.seconds - (now - history[0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Слишком много запросов. Повторите попытку через {max(retry_after, 1)} сек.",
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        self._records[key].append(now)


auth_rate_limiter = SlidingWindowRateLimiter(times=5, seconds=60, name="auth")
scan_rate_limiter = SlidingWindowRateLimiter(times=5, seconds=60, name="scan")
cleanup_rate_limiter = SlidingWindowRateLimiter(times=3, seconds=60, name="cleanup")
support_rate_limiter = SlidingWindowRateLimiter(times=5, seconds=60, name="support")
