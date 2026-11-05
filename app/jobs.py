import random
import time

from bson import ObjectId
from rq import get_current_job

from pymongo.errors import DuplicateKeyError
from app.db import contacts, enrollments, sequences, sends
from app.timing import now, due_at
from app.cache import invalidate_search_cache
from app.db import contacts

# Pretend data provider (in real life this would be an external API)
FAKE_COMPANY_DATA = {
    "shopify.com": {"industry": "E-commerce", "employees": "8000+", "hq": "Ottawa"},
    "clio.com": {"industry": "Legal Tech", "employees": "1000+", "hq": "Vancouver"},
    "stripe.com": {"industry": "Payments", "employees": "8000+", "hq": "San Francisco"},
}


def enrich_contact(contact_id: str) -> str:
    _id = ObjectId(contact_id)
    contact = contacts.find_one({"_id": _id})
    if not contact:
        return "contact not found"

    # Idempotency: don't redo work that's already done
    if contact.get("enrichment_status") == "enriched":
        return "already enriched"

    contacts.update_one({"_id": _id}, {"$set": {"enrichment_status": "processing"}})

    try:
        time.sleep(3)  # simulate a slow external API call

        if random.random() < 0.3:  # simulate the provider failing 30% of the time
            raise RuntimeError("Simulated provider timeout")

        domain = contact["email"].split("@")[-1]
        data = FAKE_COMPANY_DATA.get(domain, {})

        contacts.update_one(
            {"_id": _id},
            {"$set": {
                "domain": domain,
                **{f"company_{k}": v for k, v in data.items()},
                "enrichment_status": "enriched",
            }},
        )
        invalidate_search_cache()   # the contact changed, so cached searches are stale
        return "enriched"

    except Exception:
        job = get_current_job()
        if job and not job.retries_left:  # last attempt failed → give up
            contacts.update_one({"_id": _id}, {"$set": {"enrichment_status": "failed"}})
        raise   # re-raise so RQ knows it failed (and retries if attempts are left)


def render(template: str, contact: dict) -> str:
    first_name = contact["name"].split()[0]
    return (template
            .replace("{{first_name}}", first_name)
            .replace("{{company}}", contact.get("company") or "your company"))


def send_step(enrollment_id: str, step_index: int) -> str:
    eid = ObjectId(enrollment_id)
    enrollment = enrollments.find_one({"_id": eid})

    # Stop if they replied, or if this job is outdated
    if not enrollment or enrollment["status"] != "active":
        return "skipped: not active"
    if enrollment["current_step"] != step_index:
        return "skipped: step already done"

    seq = sequences.find_one({"_id": enrollment["sequence_id"]})
    contact = contacts.find_one({"_id": enrollment["contact_id"]})
    step = seq["steps"][step_index]

    # Record the send first. The unique index guarantees a step is sent at most once,
    # even if this job runs twice.
    try:
        sends.insert_one({"enrollment_id": eid, "step_index": step_index, "sent_at": now()})
        already_sent = False
    except DuplicateKeyError:
        already_sent = True

    if not already_sent:
        # Simulated send. A real system would call an email provider here.
        print(f"[SEND] to={contact['email']} step={step_index + 1}/{len(seq['steps'])} "
              f"subject={render(step['subject'], contact)!r}", flush=True)

    # Move to the next step (or finish). The filter makes this safe to run twice.
    next_index = step_index + 1
    if next_index < len(seq["steps"]):
        update = {"current_step": next_index,
                  "next_run_at": due_at(enrollment["enrolled_at"], seq["steps"][next_index]["day"])}
    else:
        update = {"current_step": next_index, "status": "completed", "next_run_at": None}

    enrollments.update_one(
        {"_id": eid, "status": "active", "current_step": step_index},
        {"$set": update},
    )
    return "already sent" if already_sent else "sent"