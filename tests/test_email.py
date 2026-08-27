from app import app, send_otp_email
with app.app_context():
    print(send_otp_email("kalmeshwargurav1028@gmail.com", "123456"))
