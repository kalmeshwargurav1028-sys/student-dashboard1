import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, mail, Message

def test_send_email():
    with app.app_context():
        # Override to enable TLS just in case, since Gmail port 587 requires TLS
        app.config['MAIL_USE_TLS'] = True
        
        print("Attempting to send test email via Flask-Mail...")
        print(f"MAIL_SERVER: {app.config['MAIL_SERVER']}")
        print(f"MAIL_PORT: {app.config['MAIL_PORT']}")
        print(f"MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
        
        try:
            msg = Message(
                subject="Test Email from Student Dashboard",
                sender=app.config['MAIL_USERNAME'],
                recipients=[app.config['MAIL_USERNAME']] # Send to itself for testing
            )
            msg.body = "This is a test email to verify SMTP configuration is working correctly."
            
            mail.send(msg)
            print("Test email sent successfully!")
        except Exception as e:
            print(f"Failed to send email. Error: {e}")

if __name__ == "__main__":
    test_send_email()
