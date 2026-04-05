from db import resumes_collection

test = {
    "name": "Sibyl Test",
    "status": "connected"
}

resumes_collection.insert_one(test)

print("Connected successfully!")