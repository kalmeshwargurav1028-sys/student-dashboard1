from pymongo import MongoClient
import json
from bson import json_util

db = MongoClient('mongodb://localhost:27017/').kalmeshwar
students = list(db.students.find({}))
print(json.dumps(students[:2], default=json_util.default, indent=2))
