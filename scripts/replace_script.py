import re

with open('app.py', 'r') as f:
    content = f.read()

content = content.replace("student = db.students.find_one({'id': student_id}, {'_id': 0})", "student = db.students.find_one(get_student_query({'id': student_id}), {'_id': 0})")
content = content.replace("student = db.students.find_one({'id': session.get('user_id')})", "student = db.students.find_one(get_student_query({'id': session.get('user_id')}))")

with open('app.py', 'w') as f:
    f.write(content)
