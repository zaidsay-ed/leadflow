import os
from fastapi import Header, HTTPException

from app.cache import r

RATE_LIMIT = int(os.getenv("RATE_LIMIT", "5"))          # max requests per window
WINDOW_SECONDS = int(os.getenv("RATE_WINDOW", "60"))   # window length in seconds


def rate_limit(x_api_key: str | None = Header(default=None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    key = f"rate:{x_api_key}"

    # Run INCR and EXPIRE together as one atomic step
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, WINDOW_SECONDS, nx=True)   # only set expiry if none exists yet
    count, _ = pipe.execute()

    if count > RATE_LIMIT:
        retry_after = r.ttl(key)
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )