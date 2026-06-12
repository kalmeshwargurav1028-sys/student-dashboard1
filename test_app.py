from app import app
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['logged_in'] = True
        sess['role'] = 'teacher'
    res = client.post('/api/alerts/delete/507f1f77bcf86cd799439011')
    print("Delete Response:", res.status_code, res.get_json())
