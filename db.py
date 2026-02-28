import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Use localhost fallback for local development if NO MONGO_URI is found
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client['docuchain_db']

users_collection = db['users']
requests_collection = db['requests']
blockchain_collection = db['blockchain']
