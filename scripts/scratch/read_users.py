from pymongo import MongoClient

def main():
    client = MongoClient("mongodb://localhost:27017/")
    db = client['kalmeshwar']
    users = list(db['users'].find({}))
    for user in users:
        print(f"Email: {user.get('email')}, Password: {user.get('password')}, Verified: {user.get('verified')}")

if __name__ == '__main__':
    main()
