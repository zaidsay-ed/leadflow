import os
from datetime import datetime, timedelta, timezone

# 86400 = a real day. Set to 10 in docker-compose for testing.
DAY_SECONDS = int(os.getenv("DAY_SECONDS", "86400"))


def now() -> datetime:
    return datetime.now(timezone.utc)


def due_at(start: datetime, day: int) -> datetime:
    return start + timedelta(seconds=day * DAY_SECONDS)