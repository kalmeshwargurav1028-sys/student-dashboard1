import sys
import os
from app import app, mail, Message, send_otp_email

with app.app_context():
    print("Testing send_otp_email to kalmeshwarvinayakgurav@gmail.com...")
    send_otp_email('kalmeshwarvinayakgurav@gmail.com', '123456')
