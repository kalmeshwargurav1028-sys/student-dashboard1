import sys
from app import app, db

def test_attendance():
    # Setup test client
    app.testing = True
    client = app.test_client()
    
    with client.session_transaction() as sess:
        # Mock logged in session
        sess['logged_in'] = True
        sess['user_id'] = 'test_user'
        
    # Get initial count
    initial_docs = list(db.attendance.find({}))
    print(f"Initial attendance docs count: {len(initial_docs)}")
    
    # Simulate POST request
    data = {
        'date': '2026-05-26',
        'status_IND001': 'Absent',
        'status_IND002': 'Absent'
    }
    
    print("Sending POST request to /attendance...")
    response = client.post('/attendance', data=data, follow_redirects=True)
    
    print(f"Response Status Code: {response.status_code}")
    
    if response.status_code == 500:
        print("Error 500 occurred!")
        print(response.data.decode('utf-8')[:500])
        
    # Get new count
    final_docs = list(db.attendance.find({}))
    print(f"Final attendance docs count: {len(final_docs)}")
    
    # Check if doc exists
    doc = db.attendance.find_one({'date': '2026-05-26'})
    if doc:
        print(f"Document found for 2026-05-26: {doc['records']}")
    else:
        print("Document NOT found for 2026-05-26!")

if __name__ == '__main__':
    test_attendance()
