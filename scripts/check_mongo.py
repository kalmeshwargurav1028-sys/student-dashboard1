import os
from pymongo import MongoClient

mongo_uri = os.environ.get("MONGO_URI", "mongodb+srv://kalmeshwar01:Kalmeshwar@studentdashboard2.estzsbf.mongodb.net/?appName=studentDashboard2")
client = MongoClient(mongo_uri)
db = client['kalmeshwar']

settings = db.settings.find_one({})
print("Settings in DB:", settings)
