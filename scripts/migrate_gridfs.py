import os
from pymongo import MongoClient
import gridfs
from dotenv import load_dotenv

load_dotenv()
mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(mongo_uri)
db = client['kalmeshwar']
fs = gridfs.GridFS(db)

def migrate_student_photos():
    students = db.students.find({"photo_url": {"$regex": "^/static/uploads/"}})
    for student in students:
        old_url = student['photo_url']
        # e.g. /static/uploads/129be273_suraj.jpeg
        filename = old_url.split('/')[-1]
        filepath = os.path.join('static', 'uploads', filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                content_type = 'image/jpeg' if filename.endswith('.jpeg') or filename.endswith('.jpg') else 'image/png'
                file_id = fs.put(f, filename=filename, content_type=content_type)
                
            new_url = f"/file/{file_id}"
            db.students.update_one({'_id': student['_id']}, {'$set': {'photo_url': new_url}})
            print(f"Migrated student photo: {filename}")
        else:
            print(f"File missing: {filepath}")

def migrate_admin_photos():
    admins = db.users.find({"photo_url": {"$regex": "^/static/uploads/"}})
    for admin in admins:
        old_url = admin['photo_url']
        filename = old_url.split('/')[-1]
        filepath = os.path.join('static', 'uploads', filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                content_type = 'image/jpeg' if filename.endswith('.jpeg') or filename.endswith('.jpg') else 'image/png'
                file_id = fs.put(f, filename=filename, content_type=content_type)
                
            new_url = f"/file/{file_id}"
            db.users.update_one({'_id': admin['_id']}, {'$set': {'photo_url': new_url}})
            print(f"Migrated admin photo: {filename}")
        else:
            print(f"File missing: {filepath}")

def migrate_materials():
    materials = db.materials.find({"file_url": {"$regex": "^/static/uploads/materials/"}})
    for material in materials:
        old_url = material['file_url']
        filename = old_url.split('/')[-1]
        filepath = os.path.join('static', 'uploads', 'materials', filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                file_id = fs.put(f, filename=filename, content_type='application/pdf')
                
            new_url = f"/file/{file_id}"
            db.materials.update_one({'_id': material['_id']}, {'$set': {'file_url': new_url}})
            print(f"Migrated material: {filename}")
        else:
            print(f"File missing: {filepath}")

if __name__ == "__main__":
    print("Starting GridFS migration...")
    migrate_student_photos()
    migrate_admin_photos()
    migrate_materials()
    print("Migration complete!")
