import random
import time

from bson import ObjectId
from rq import get_current_job

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