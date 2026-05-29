from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db = client['kalmesh_db']

with open('mongo_test_out.txt', 'w') as f:
    f.write("Attendance Documents:\n")
    for doc in db.attendance.find({}):
        f.write(f"{doc['date']} - {doc['records']}\n")
