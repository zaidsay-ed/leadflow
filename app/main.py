import json

from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.cache import r, search_version, invalidate_search_cache
from app.db import contacts, CASE_INSENSITIVE
from app.models import ContactCreate, ContactUpdate
from app.rate_limit import rate_limit
from app.queue import enrichment_queue, redis_conn

from rq import Retry
from rq.exceptions import NoSuchJobError
from rq.job import Job

app = FastAPI(title="LeadFlow", dependencies=[Depends(rate_limit)])

def serialize(doc: dict) -> dict:
    """Convert Mongo's _id (ObjectId) into a plain string id."""
    doc["id"] = str(doc.pop("_id"))
    return doc


def to_object_id(contact_id: str) -> ObjectId:
    if not ObjectId.is_valid(contact_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    return ObjectId(contact_id)


@app.get("/")
def home():
    return {"message": "LeadFlow is running"}


@app.post("/contacts", status_code=201)
def create_contact(contact: ContactCreate):
    doc = contact.model_dump()
    try:
        result = contacts.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Contact with this email already exists")
    doc["_id"] = result.inserted_id
    invalidate_search_cache()
    return serialize(doc)


@app.get("/contacts")
def search_contacts(
    company: str | None = None,
    title: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    # Lowercase the key parts so "Shopify" and "shopify" share one cache entry
    key = (
        f"search:v{search_version()}:"
        f"{(company or '').lower()}:{(title or '').lower()}:{page}:{page_size}"
    )

    cached = r.get(key)
    if cached:
        result = json.loads(cached)
        result["source"] = "cache"
        return result

    filters = {}
    if company:
        filters["company"] = company
    if title:
        filters["title"] = title

    cursor = (
        contacts.find(filters)
        .collation(CASE_INSENSITIVE)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    result = {
        "page": page,
        "page_size": page_size,
        "total": contacts.count_documents(filters, collation=CASE_INSENSITIVE),
        "results": [serialize(d) for d in cursor],
    }

    r.set(key, json.dumps(result), ex=60)   # cache for 60 seconds
    result["source"] = "database"
    return result


@app.get("/contacts/{contact_id}")
def get_contact(contact_id: str):
    doc = contacts.find_one({"_id": to_object_id(contact_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Contact not found")
    return serialize(doc)


@app.patch("/contacts/{contact_id}")
def update_contact(contact_id: str, update: ContactUpdate):
    changes = update.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        doc = contacts.find_one_and_update(
            {"_id": to_object_id(contact_id)},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Email already in use")
    if not doc:
        raise HTTPException(status_code=404, detail="Contact not found")
    invalidate_search_cache()
    return serialize(doc)


@app.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: str):
    result = contacts.delete_one({"_id": to_object_id(contact_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    invalidate_search_cache()
    return Response(status_code=204)


@app.post("/contacts/{contact_id}/enrich", status_code=202)
def enrich_contact(contact_id: str):
    oid = to_object_id(contact_id)

    # Atomically mark as queued, but only if it isn't already queued or processing.
    # One database operation means two simultaneous requests can't both get through.
    doc = contacts.find_one_and_update(
        {"_id": oid, "enrichment_status": {"$nin": ["queued", "processing"]}},
        {"$set": {"enrichment_status": "queued"}},
    )
    if not doc:
        if contacts.count_documents({"_id": oid}) == 0:
            raise HTTPException(status_code=404, detail="Contact not found")
        raise HTTPException(status_code=409, detail="Enrichment already in progress")

    job = enrichment_queue.enqueue(
        "app.jobs.enrich_contact",
        contact_id,
        retry=Retry(max=3, interval=[5, 10, 20]),   # retry up to 3 times, waiting longer each time
    )
    return {"job_id": job.id, "status": "queued"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "status": job.get_status(),
        "result": job.return_value(),
    }