from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(mongo_uri)
db = client['kalmeshwar']
users = db['users']
t = users.find_one({'role': 'teacher'})
if t:
    print(str(t['_id']))
else:
    print("NO TEACHER")
