from pymongo import MongoClient
import os

client = MongoClient(os.getenv('MONGO_URI', "mongodb+srv://student1:indus123@cluster0.estzsbf.mongodb.net/school_management?retryWrites=true&w=majority&appName=Cluster0"))
db = client.get_database()
config = db.role_permissions.find_one({'_id': 'global_config'})
print(config)
