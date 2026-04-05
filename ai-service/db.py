import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGO_URI)

# select database
db = client["sibyl"]

# select collections
resumes_collection = db["resumes"]
jobs_collection = db["jobs"]