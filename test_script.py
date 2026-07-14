from app import app, db

app.config['TESTING'] = True

with app.test_client() as client:
    with client.session_transaction() as sess:
        student = db.students.find_one()
        sess['logged_in'] = True
        sess['role'] = 'student'
        sess['user_id'] = student['id']
        sess['username'] = student.get('name')
        
    try:
        res = client.get('/student/home')
        print("Home status:", res.status_code)
        if res.status_code == 500:
            print(res.text)
    except Exception as e:
        import traceback
        traceback.print_exc()

