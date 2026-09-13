import pytest
from fastapi import HTTPException
from utils.rate_limiter import SlidingWindowRateLimiter

@pytest.mark.asyncio
async def test_sliding_window_rate_limiter():
    limiter = SlidingWindowRateLimiter(times=3, seconds=10, name='test')
    key = 'user_999'

    # First 3 requests succeed
    await limiter.check(key)
    await limiter.check(key)
    await limiter.check(key)

    # 4th request must raise 429
    with pytest.raises(HTTPException) as exc_info:
        await limiter.check(key)
    assert exc_info.value.status_code == 429
    assert 'Слишком много запросов' in exc_info.value.detail

    # Another user is isolated and succeeds
    await limiter.check('user_888')
