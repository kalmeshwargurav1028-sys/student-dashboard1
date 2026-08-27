from pymongo import MongoClient
client = MongoClient('mongodb://localhost:27017/')
db = client['kalmeshwar']

# Delete all old students
db.students.delete_many({})

# Insert the new one
new_student = {
    'id': 'IND002',
    'name': 'Nitin Gurav',
    'dob': '2005-04-12',
    'age': '21',
    'gender': 'Male',
    'phone': '9845321076',
    'email': 'nitingurav.tech@gmail.com',
    'photo_url': '/static/uploads/nitin_profile.jpg',  # We'll use a placeholder/mock if file doesn't exist
    'board': 'State Board',
    'student_class': '12th',
    'division': 'A',
    'academic_year': '2026',
    'roll_number': '15',
    'parent_name': 'Anand',
    'relationship': 'Father',
    'parent_phone': '9845398765',
    'parent_email': 'anandgurav68@gmail.com',
    'occupation': 'Engineer',
    'address': '2nd Cross, Electronic City Phase 1',
    'city': 'Bangalore',
    'state': 'Karnataka',
    'pincode': '560100',
    'attendance': '100',
    'performance': '80'
}

db.students.insert_one(new_student)
print("Database updated successfully.")
