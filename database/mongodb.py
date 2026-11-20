import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

# Locate the project root and load environment variables
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# MongoDB configuration
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://127.0.0.1:27017/"
)

MONGODB_DATABASE = os.getenv(
    "MONGODB_DATABASE",
    "urban_risk_db"
)

# Create MongoDB client
client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000
)

# Select project database
db = client[MONGODB_DATABASE]


def get_database():
    """Return the MongoDB database instance."""
    return db


def check_mongodb_connection():
    """Check whether MongoDB is reachable."""
    return client.admin.command("ping")


def close_mongodb_connection():
    """Close the MongoDB client."""
    client.close()


if __name__ == "__main__":
    try:
        result = check_mongodb_connection()

        print("========== MONGODB CONNECTION ==========")
        print("Connection: Successful")
        print("Database:", MONGODB_DATABASE)
        print("Ping:", result["ok"])

    except Exception as error:
        print("MongoDB connection failed.")
        print("Error:", error)

