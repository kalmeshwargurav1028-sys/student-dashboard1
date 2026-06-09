from app import app
import json

with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['logged_in'] = True
        sess['role'] = 'admin'
        sess['user_id'] = 'dummy'
    
    response = c.post('/api/announcements', json={
        'audience': 'all',
        'title': 'Test',
        'body': 'Test body',
        'expiry_date': '2026-12-31'
    })
    print("STATUS:", response.status_code)
    print("JSON:", response.json)
