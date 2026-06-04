import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Source: Local MongoDB
source_client = MongoClient("mongodb://localhost:27017/")
source_db = source_client['kalmeshwar']

# Destination: Atlas MongoDB
target_uri = os.environ.get("MONGO_URI")

# Safety check
if not target_uri or "localhost" in target_uri:
    print("❌ ERROR: Your MONGO_URI in the .env file is still pointing to localhost.")
    print("Please open your .env file and change MONGO_URI to your new MongoDB Atlas connection string.")
    print("Example: MONGO_URI=mongodb+srv://<username>:<password>@cluster0...mongodb.net/")
    exit(1)

print("Connecting to MongoDB Atlas...")
try:
    target_client = MongoClient(target_uri)
    target_db = target_client['kalmeshwar']
    # Trigger a test command to ensure connection works
    target_client.admin.command('ping')
    print("✅ Successfully connected to MongoDB Atlas!\n")
except Exception as e:
    print("❌ ERROR: Could not connect to MongoDB Atlas. Please check your username, password, and connection string.")
    print(e)
    exit(1)

collections_to_sync = source_db.list_collection_names()

print(f"Starting migration of {len(collections_to_sync)} collections from Local -> Atlas...")

for coll_name in collections_to_sync:
    print(f"Syncing collection: '{coll_name}'...")
    docs = list(source_db[coll_name].find({}))
    if docs:
        # Clear the old collection in Atlas and insert the new documents
        target_db[coll_name].drop() 
        target_db[coll_name].insert_many(docs)
        print(f"  -> ✅ Migrated {len(docs)} documents.")
    else:
        print(f"  -> ℹ️ Collection is empty. Skipped.")

print("\n🎉 Migration to Atlas completely finished! Your Vercel app should now work perfectly.")
