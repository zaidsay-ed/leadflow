import os
from redis import Redis
from rq import Queue

# RQ needs its own connection that returns raw bytes,
# so we don't reuse the cache connection (which decodes to strings)
redis_conn = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))

enrichment_queue = Queue("enrichment", connection=redis_conn)
sequence_queue = Queue("sequences", connection=redis_conn)