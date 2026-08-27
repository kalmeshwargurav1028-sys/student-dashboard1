import sys
import os
from app import app, mail, Message, send_otp_email

with app.app_context():
    print("Testing send_otp_email...")
    send_otp_email('agent4@indusschool.com', '123456')
