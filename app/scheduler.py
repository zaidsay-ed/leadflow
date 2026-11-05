import time

from rq import Retry

from app.db import enrollments
from app.queue import sequence_queue
from app.timing import now

POLL_SECONDS = 2


def queue_due_steps() -> None:
    while True:
        # Atomically claim one due enrollment by clearing next_run_at.
        # Even with several schedulers running, each enrollment is claimed only once.
        enrollment = enrollments.find_one_and_update(
            {"status": "active", "next_run_at": {"$lte": now()}},
            {"$set": {"next_run_at": None}},
        )
        if not enrollment:
            return
        sequence_queue.enqueue(
            "app.jobs.send_step",
            str(enrollment["_id"]),
            enrollment["current_step"],
            retry=Retry(max=3, interval=[5, 10, 20]),
        )
        print(f"[SCHEDULER] queued step {enrollment['current_step'] + 1} "
              f"for enrollment {enrollment['_id']}", flush=True)


if __name__ == "__main__":
    print("Scheduler started", flush=True)
    while True:
        queue_due_steps()
        time.sleep(POLL_SECONDS)