import requests
session = requests.Session()
# First login
data = {'role': 'student', 'email': 'student@gmail.com', 'password': 'password'} # We don't know the password
# Let's bypass by creating a test app context
