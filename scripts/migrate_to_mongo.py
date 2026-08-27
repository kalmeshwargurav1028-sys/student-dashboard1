import os
import json
import sqlite3
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Connect to MongoDB
mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(mongo_uri)

# Create a new database for your application
# (In Compass, you'll see this new database appear after we insert data)
db = client['kalmeshwar']

def migrate():
    print("Starting migration to MongoDB...")

    # 1. Migrate sqlite users
    print("\nMigrating users from sqlite...")
    try:
        if os.path.exists('data/database.db'):
            conn = sqlite3.connect('data/database.db')
            conn.row_factory = sqlite3.Row
            users = conn.execute("SELECT * FROM users").fetchall()
            
            if users:
                users_data = [dict(u) for u in users]
                db.users.drop()
                db.users.insert_many(users_data)
                print(f"Successfully inserted {len(users_data)} users into 'users' collection.")
            else:
                print("No users found in sqlite database.")
            conn.close()
        else:
            print("No sqlite database found.")
    except Exception as e:
        print("Error migrating users:", e)

    # 2. Migrate students
    print("\nMigrating students from JSON...")
    try:
        if os.path.exists('data/students.json'):
            with open('data/students.json', 'r') as f:
                students = json.load(f)
                if students:
                    db.students.drop()
                    db.students.insert_many(students)
                    print(f"Successfully inserted {len(students)} students into 'students' collection.")
                else:
                    print("No students found in JSON.")
        else:
            print("No students.json found.")
    except Exception as e:
        print("Error migrating students:", e)

    # 3. Migrate attendance
    print("\nMigrating attendance from JSON...")
    try:
        if os.path.exists('data/attendance.json'):
            with open('data/attendance.json', 'r') as f:
                attendance = json.load(f)
                if attendance:
                    attendance_docs = []
                    for date_str, records in attendance.items():
                        attendance_docs.append({
                            "date": date_str,
                            "records": records
                        })
                    if attendance_docs:
                        db.attendance.drop()
                        db.attendance.insert_many(attendance_docs)
                        print(f"Successfully inserted {len(attendance_docs)} attendance days into 'attendance' collection.")
                else:
                    print("No attendance records found.")
        else:
            print("No attendance.json found.")
    except Exception as e:
        print("Error migrating attendance:", e)

    # 4. Migrate settings
    print("\nMigrating settings from JSON...")
    try:
        if os.path.exists('data/settings.json'):
            with open('data/settings.json', 'r') as f:
                settings = json.load(f)
                if settings:
                    db.settings.drop()
                    if isinstance(settings, dict):
                        db.settings.insert_one(settings)
                    elif isinstance(settings, list):
                        db.settings.insert_many(settings)
                    print("Successfully inserted settings into 'settings' collection.")
                else:
                    print("No settings found in JSON.")
        else:
            print("No settings.json found.")
    except Exception as e:
        print("Error migrating settings:", e)

    # 5. Migrate reports
    print("\nMigrating reports from JSON...")
    try:
        if os.path.exists('data/reports.json'):
            with open('data/reports.json', 'r') as f:
                reports = json.load(f)
                if reports:
                    db.reports.drop()
                    if isinstance(reports, list):
                        db.reports.insert_many(reports)
                    elif isinstance(reports, dict):
                        db.reports.insert_one(reports)
                    print(f"Successfully inserted reports into 'reports' collection.")
                else:
                    print("No reports found in JSON.")
        else:
            print("No reports.json found.")
    except Exception as e:
        print("Error migrating reports:", e)

    print("\nMigration complete! You can now view 'kalmeshwar' in MongoDB Compass.")

if __name__ == "__main__":
    migrate()
