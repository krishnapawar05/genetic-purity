import sys
import os
import re
from dotenv import load_dotenv
import certifi
from pymongo import MongoClient, ASCENDING, DESCENDING

# Ensure environment variables are loaded FIRST
load_dotenv()

_client = None
_db = None

def mask_mongo_uri(uri: str) -> str:
    """Masks password in MongoDB connection URI for secure log output."""
    if not uri:
        return ""
    return re.sub(r'://([^:]+):([^@]+)@', r'://\1:********@', uri)

def get_db():
    """
    Returns singleton pymongo Database object.
    Initializes single MongoClient using certifi CA bundle for secure SSL/TLS.
    Performs startup ping test and raises RuntimeError if connection fails.
    """
    global _client, _db
    if _db is None:
        mongo_uri = os.getenv("MONGO_URI", "").strip()
        db_name = os.getenv("DB_NAME", "").strip()

        if not mongo_uri:
            raise RuntimeError("MONGO_URI is not configured. Please check your .env file and set your MongoDB Atlas connection string.")

        if not db_name:
            raise RuntimeError("DB_NAME is not configured. Please check your .env file and set your database name.")

        masked_uri = mask_mongo_uri(mongo_uri)
        print(f"[MongoDB Atlas Startup] Connecting to: {masked_uri}")

        try:
            # Single MongoClient instance with certifi SSL CA bundle & 30s timeout
            _client = MongoClient(
                mongo_uri,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=30000
            )
            
            # Ping connection test before Flask app proceeds
            _client.admin.command("ping")
            print("[MongoDB Atlas Startup] SSL/TLS Handshake & Ping Verified Successfully!")
            
            _db = _client[db_name]

            # Create Indexes
            users_col = _db['users']
            users_col.create_index([("email", ASCENDING)], unique=True, sparse=True)
            users_col.create_index([("mobileNumber", ASCENDING)], unique=True, sparse=True)

            otps_col = _db['otp_requests']
            otps_col.create_index([("createdAt", ASCENDING)], expireAfterSeconds=600)
            otps_col.create_index([("mobileNumber", ASCENDING)])

            preds_col = _db['predictions']
            preds_col.create_index([("userId", ASCENDING), ("createdAt", DESCENDING)])

            pmts_col = _db['payments']
            pmts_col.create_index([("orderId", ASCENDING)], unique=True, sparse=True)
            pmts_col.create_index([("userId", ASCENDING), ("createdAt", DESCENDING)])

        except Exception as e:
            print(f"[MongoDB Atlas Connection ERROR] Ping failed for URI: {masked_uri}", file=sys.stderr)
            print(f"[MongoDB Atlas Connection ERROR] Real Exception: {e}", file=sys.stderr)
            _client = None
            _db = None
            raise RuntimeError(f"MongoDB Atlas SSL/TLS Connection Failed: {e}")

    return _db

def get_users_collection():
    db = get_db()
    return db['users']

def get_otps_collection():
    db = get_db()
    return db['otp_requests']

def get_predictions_collection():
    db = get_db()
    return db['predictions']

def get_payments_collection():
    db = get_db()
    return db['payments']
