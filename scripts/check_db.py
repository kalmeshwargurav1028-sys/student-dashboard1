from pymongo import MongoClient
import os

client = MongoClient(os.getenv('MONGO_URI', "mongodb+srv://student1:indus123@cluster0.estzsbf.mongodb.net/school_management?retryWrites=true&w=majority&appName=Cluster0"))
db = client.get_database()
user = db.users.find_one({"email": "kalmeshwarvinayakgurav@gmail.com"})
if user:
    print("User found:")
    print("Email:", user.get("email"))
    print("Password hash length:", len(user.get("password", "")))
    print("Verified:", user.get("verified"))
else:
    print("User NOT found in database")
