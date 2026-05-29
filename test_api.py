import sys
from app import app

app.config['TESTING'] = True
client = app.test_client()

with client.session_transaction() as sess:
    sess['logged_in'] = True

response = client.post('/api/dashboard_ai', json={'message': 'initial'})
print(response.status_code)
print(response.data.decode('utf-8'))
