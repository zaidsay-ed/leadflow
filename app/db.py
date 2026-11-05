import os
from pymongo import MongoClient, ASCENDING
from pymongo.collation import Collation

client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"), tz_aware=True)
db = client["leadflow"]
contacts = db["contacts"]

# Case-insensitive comparison (strength=2 ignores upper/lowercase)
CASE_INSENSITIVE = Collation(locale="en", strength=2)

# Remove the old case-sensitive index if it exists
if "company_1_title_1" in contacts.index_information():
    contacts.drop_index("company_1_title_1")

# Indexes
contacts.create_index([("email", ASCENDING)], unique=True)
contacts.create_index(
    [("company", ASCENDING), ("title", ASCENDING)],
    collation=CASE_INSENSITIVE,
    name="company_title_ci",
)

sequences = db["sequences"]
enrollments = db["enrollments"]
sends = db["sends"]

# A contact can only be enrolled once per sequence
enrollments.create_index([("sequence_id", ASCENDING), ("contact_id", ASCENDING)], unique=True)
# The scheduler's query: "active enrollments that are due"
enrollments.create_index([("status", ASCENDING), ("next_run_at", ASCENDING)])
# Idempotency: each step of each enrollment can be recorded only once
sends.create_index([("enrollment_id", ASCENDING), ("step_index", ASCENDING)], unique=True)