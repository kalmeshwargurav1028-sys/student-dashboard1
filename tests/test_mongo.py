import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv("MONGO_URI")

# Try standard connection
try:
    print("Trying standard connection...")
    client = MongoClient(uri, serverSelectionTimeoutMS=2000)
    client.admin.command('ping')
    print("Standard connection successful!")
except Exception as e:
    print(f"Standard failed: {e}")

# Try with certifi
try:
    print("\nTrying with certifi...")
    client2 = MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=2000)
    client2.admin.command('ping')
    print("Certifi connection successful!")
except Exception as e:
    print(f"Certifi failed: {e}")

# Try with tlsAllowInvalidCertificates
try:
    print("\nTrying with tlsAllowInvalidCertificates...")
    client3 = MongoClient(uri, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=2000)
    client3.admin.command('ping')
    print("tlsAllowInvalidCertificates connection successful!")
except Exception as e:
    print(f"tlsAllowInvalidCertificates failed: {e}")
