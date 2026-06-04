import os
from dotenv import load_dotenv
load_dotenv()
from pymongo import MongoClient

mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(mongo_uri)
db = client['kalmeshwar']
config_data = db.settings.find_one({}, {'_id': 0}) or {}
print(config_data.get('MAIL_USERNAME'))
print(config_data.get('MAIL_PASSWORD'))
print(config_data.get('MAIL_SERVER'))
