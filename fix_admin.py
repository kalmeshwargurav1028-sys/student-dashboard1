from app import app
from pymongo import MongoClient
import os
with app.app_context():
    from app import db
    db.admins.update_many({}, {"$set": {"email": "kalmeshwargurav1028@gmail.com"}})
    print("Admin email updated.")
