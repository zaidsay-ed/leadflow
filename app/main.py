from bson import ObjectId
from fastapi import FastAPI, HTTPException, Query, Response
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.db import contacts, CASE_INSENSITIVE
from app.models import ContactCreate, ContactUpdate

app = FastAPI(title="LeadFlow")


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
    return serialize(doc)


@app.get("/contacts")
def search_contacts(
    company: str | None = None,
    title: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
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
    return {
        "page": page,
        "page_size": page_size,
        "total": contacts.count_documents(filters, collation=CASE_INSENSITIVE),
        "results": [serialize(d) for d in cursor],
    }


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
    return serialize(doc)


@app.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: str):
    result = contacts.delete_one({"_id": to_object_id(contact_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return Response(status_code=204)