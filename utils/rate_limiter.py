import time
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import HTTPException, status

from database import db
from utils.logger import logger


class SlidingWindowRateLimiter:
    """Distributed persistent sliding-window rate limiter with database backing and in-memory fallback."""

    def __init__(self, times: int = 5, seconds: int = 60, name: str = "default"):
        self.times = times
        self.seconds = seconds
        self.name = name
        self._records: Dict[str, List[float]] = defaultdict(list)

    def _cleanup_old_memory(self, key: str, now: float) -> None:
        threshold = now - self.seconds
        self._records[key] = [t for t in self._records[key] if t > threshold]
        if not self._records[key]:
            del self._records[key]

    async def check(self, key: str) -> None:
        now = time.time()
        full_key = f"{self.name}:{key}"
        threshold = now - self.seconds

        # Attempt database-backed distributed check
        try:
            async with db.get_connection() as conn:
                await conn.execute(
                    "DELETE FROM rate_limits WHERE limiter_key = ? AND timestamp <= ?",
                    (full_key, threshold),
                )
                cur = await conn.execute(
                    "SELECT timestamp FROM rate_limits WHERE limiter_key = ? ORDER BY timestamp ASC",
                    (full_key,),
                )
                rows = await cur.fetchall()
                if len(rows) >= self.times:
                    oldest = rows[0][0]
                    retry_after = int(self.seconds - (now - oldest))
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Слишком много запросов. Повторите попытку через {max(retry_after, 1)} сек.",
                        headers={"Retry-After": str(max(retry_after, 1))},
                    )
                await conn.execute(
                    "INSERT INTO rate_limits (limiter_key, timestamp) VALUES (?, ?)",
                    (full_key, now),
                )
                await conn.commit()
                return
        except HTTPException:
            raise
        except Exception as e:
            # Fallback to robust in-memory tracking if DB is unavailable/uninitialized
            logger.debug(f"DB rate limiter fallback to memory for {full_key}: {e}")

        self._cleanup_old_memory(full_key, now)
        history = self._records[full_key]
        if len(history) >= self.times:
            retry_after = int(self.seconds - (now - history[0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Слишком много запросов. Повторите попытку через {max(retry_after, 1)} сек.",
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        self._records[full_key].append(now)


auth_rate_limiter = SlidingWindowRateLimiter(times=5, seconds=60, name="auth")
scan_rate_limiter = SlidingWindowRateLimiter(times=5, seconds=60, name="scan")
cleanup_rate_limiter = SlidingWindowRateLimiter(times=3, seconds=60, name="cleanup")
support_rate_limiter = SlidingWindowRateLimiter(times=5, seconds=60, name="support")
scheduler_rate_limiter = SlidingWindowRateLimiter(times=5, seconds=60, name="scheduler")
