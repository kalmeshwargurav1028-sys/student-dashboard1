from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv('MONGO_URI')
client = MongoClient(uri)
db = client.student_dashboard

notifs = db.notifications.find({"type": "error"}).sort("timestamp", -1).limit(5)
for n in notifs:
    print(n['timestamp'])
    print(n['message'])
    print("-" * 20)
