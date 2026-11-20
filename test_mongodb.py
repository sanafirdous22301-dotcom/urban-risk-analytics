from pymongo import MongoClient

client = MongoClient(
    "mongodb://127.0.0.1:27017/",
    serverSelectionTimeoutMS=5000
)

try:
    print(client.admin.command("ping"))
    print("MongoDB connection successful!")
finally:
    client.close()
