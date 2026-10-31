import os
from pymongo import MongoClient, ASCENDING

client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"))
db = client["leadflow"]
contacts = db["contacts"]

# Indexes: make searches fast and block duplicate emails
contacts.create_index([("email", ASCENDING)], unique=True)
contacts.create_index([("company", ASCENDING), ("title", ASCENDING)])