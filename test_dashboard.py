import sys
from app import app
from flask import session

with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['logged_in'] = True
        sess['user_id'] = '6662e3d81234567890abcdef'
        sess['role'] = 'teacher'
        sess['username'] = 'Test Teacher'
        sess['name'] = 'Test Teacher'
        sess['email'] = 'test@example.com'
    
    response = c.get('/dashboard')
    print(f"Status Code: {response.status_code}")
    if response.status_code == 500:
        print(response.data.decode('utf-8'))
