import smtplib
from email.mime.text import MIMEText

def test_smtp_login():
    email = "agent4@indusschool.com"
    password = "Agent@2026"
    server = "smtp.office365.com"
    port = 587
    
    print(f"Connecting to {server}:{port}...")
    try:
        smtp = smtplib.SMTP(server, port, timeout=15)
        smtp.set_debuglevel(1)
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        print(f"Attempting to login with {email}...")
        smtp.login(email, password)
        print("Login successful! The credentials work.")
        
        # Optionally send an email
        msg = MIMEText("This is a test email to verify Microsoft 365 SMTP configuration.")
        msg['Subject'] = 'Test Email from SMTP Test Script (Office365)'
        msg['From'] = email
        msg['To'] = email
        
        print("Sending test email to self...")
        smtp.sendmail(email, [email], msg.as_string())
        print("Email sent successfully!")
        
        smtp.quit()
    except Exception as e:
        print(f"Failed to connect or login. Error: {e}")

if __name__ == "__main__":
    test_smtp_login()
