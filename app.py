import json
import os
import uuid
import random
import string
import csv
import io
from datetime import datetime, timedelta
import threading
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, make_response, send_file, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from google import genai
from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient
import sendgrid
from sendgrid.helpers.mail import Mail as SendGridMail
from pymongo import MongoClient
from bson.objectid import ObjectId
import gridfs
import smtplib
from email.mime.text import MIMEText

load_dotenv()

# Setup MongoDB
# Vercel Serverless Optimization: Restrict maxPoolSize so 940 simultaneous users don't crash MongoDB Atlas free tier (500 conn limit)
mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(
    mongo_uri, 
    maxPoolSize=1, 
    minPoolSize=0, 
    maxIdleTimeMS=10000, 
    serverSelectionTimeoutMS=5000
)
db = client['kalmeshwar']
users = db['users']
fs = gridfs.GridFS(db)



# Helper Functions for Notifications
def send_twilio_sms(phone, message):
    config_data = db.settings.find_one({}, {'_id': 0}) or {}
    account_sid = config_data.get('TWILIO_ACCOUNT_SID') or os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = config_data.get('TWILIO_AUTH_TOKEN') or os.environ.get('TWILIO_AUTH_TOKEN')
    from_phone = config_data.get('TWILIO_PHONE_NUMBER') or os.environ.get('TWILIO_PHONE_NUMBER')
    
    if not (account_sid and auth_token and from_phone):
        print(f"[MOCK SMS] To: {phone} - Message: {message}")
        return

    try:
        client = TwilioClient(account_sid, auth_token)
        message = client.messages.create(
            body=message,
            from_=from_phone,
            to=phone
        )
        print(f"SMS sent successfully: {message.sid}")
    except Exception as e:
        print(f"Failed to send SMS to {phone}: {e}")

def send_sendgrid_email(email, subject, message_body):
    config_data = db.settings.find_one({}, {'_id': 0}) or {}
    api_key = config_data.get('SENDGRID_API_KEY') or os.environ.get('SENDGRID_API_KEY')
    from_email = config_data.get('SENDGRID_FROM_EMAIL') or os.environ.get('SENDGRID_FROM_EMAIL')
    
    if not (api_key and from_email):
        print(f"[MOCK EMAIL] To: {email} - Subject: {subject} - Body: {message_body}")
        return

    try:
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        message = SendGridMail(
            from_email=from_email,
            to_emails=email,
            subject=subject,
            plain_text_content=message_body
        )
        response = sg.send(message)
        print(f"Email sent successfully: {response.status_code}")
    except Exception as e:
        print(f"Failed to send email via SMTP: {str(e)}")
        return False

def send_error_email(error_details):
    try:
        config_data = db.settings.find_one({}, {'_id': 0}) or {}
    except Exception:
        config_data = {}

    smtp_server = config_data.get('MAIL_SERVER', 'smtp.office365.com')
    smtp_port = int(config_data.get('MAIL_PORT', 587))
    smtp_user = config_data.get('MAIL_USERNAME', 'agent4@indusschool.com')
    smtp_pass = config_data.get('MAIL_PASSWORD', 'Agent@2026')
    admin_email = 'kalmeshwargurav1028@gmail.com'

    subject = "CRITICAL: System Error Alert"
    body = f"An unhandled exception occurred in the Student Dashboard:\n\n{error_details}"
    
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = admin_email

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send error alert email: {str(e)}")
        return False

def configure_gemini():
    config_data = db.settings.find_one({}, {'_id': 0}) or {}
    api_key = config_data.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
    if api_key:
        client = genai.Client(api_key=api_key)
        return client, api_key
    return None, None

configure_gemini()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_change_in_production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

@app.context_processor
def inject_global_context():
    context = {'active_announcements': [], 'role_permissions': {}}
    if not session.get('logged_in'):
        return context
    
    role = session.get('role', 'student')
    target = ['all']
    if role in ('admin', 'teacher'):
        target.append('teachers')
    if role == 'student':
        target.append('students')
        
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')
        announcements = list(db.announcements.find({
            'audience': {'$in': target},
            'expiry_date': {'$gte': today_str}
        }).sort('date_sent', -1))
        context['active_announcements'] = announcements
    except Exception as e:
        print(f"Error fetching announcements: {e}")
        
    try:
        if role == 'admin':
            context['role_permissions'] = {
                'view_dashboard': True,
                'manage_students': True,
                'edit_materials': True,
                'modify_attendance': True,
                'view_system_health': True,
                'send_announcements': True,
                'ai_insights': True
            }
        else:
            global_config = db.role_permissions.find_one({'_id': 'global_config'})
            if global_config and global_config.get(role):
                context['role_permissions'] = global_config[role]
            else:
                # Defaults
                if role == 'teacher':
                    context['role_permissions'] = {'view_dashboard': True, 'manage_students': True, 'edit_materials': True, 'modify_attendance': True}
                else:
                    context['role_permissions'] = {'view_dashboard': True}
                    
        # Failsafe
        if not context.get('role_permissions'):
            context['role_permissions'] = {}
            
    except Exception as e:
        print(f"Error fetching role permissions: {e}")
        context['role_permissions'] = {}

    return context

@app.route('/api/role_permissions', methods=['POST'])
def update_role_permissions():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    try:
        data = request.json
        db.role_permissions.update_one(
            {'_id': 'global_config'},
            {'$set': data},
            upsert=True
        )
        
        log_notification(
            "System Config Updated", 
            "Global role permissions have been successfully modified.", 
            type='success', 
            role_target='admin'
        )
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roles/add', methods=['POST'])
def add_custom_role():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    try:
        data = request.json
        role_name = data.get('role')
        if not role_name or not isinstance(role_name, str):
            return jsonify({'success': False, 'error': 'Invalid role name'}), 400
            
        role_name = role_name.strip().lower()
        if role_name == 'admin' or role_name == '_id':
            return jsonify({'success': False, 'error': 'Reserved role name'}), 400
            
        # Default permissions for a new role
        default_permissions = {
            'view_dashboard': False,
            'manage_students': False,
            'edit_materials': False,
            'modify_attendance': False,
            'view_system_health': False,
            'send_announcements': False,
            'ai_insights': False
        }
        
        # Upsert the new role into global_config
        db.role_permissions.update_one(
            {'_id': 'global_config'},
            {'$set': {role_name: default_permissions}},
            upsert=True
        )
        
        log_notification(
            "Custom Role Added", 
            f"A new role '{role_name}' has been created.", 
            type='success', 
            role_target='admin'
        )
        
        return jsonify({'success': True, 'role': role_name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/announcements', methods=['POST'])
def create_announcement():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    try:
        data = request.json
        audience = data.get('audience', 'all')
        title = data.get('title', '')
        body = data.get('body', '')
        expiry_date = data.get('expiry_date', '')
        
        if not title or not body or not expiry_date:
            return jsonify({'success': False, 'error': 'Missing fields'}), 400
            
        db.announcements.insert_one({
            'title': title,
            'body': body,
            'audience': audience,
            'expiry_date': expiry_date,
            'date_sent': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'author_id': session.get('user_id')
        })
        
        # Map plural audience to singular role target
        role_map = {
            'all': 'all',
            'teachers': 'teacher',
            'students': 'student'
        }
        log_notification(f"📢 {title}", body, type='info', role_target=role_map.get(audience, 'all'))
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/announcements/<ann_id>', methods=['DELETE'])
def delete_announcement(ann_id):
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    try:
        from bson.objectid import ObjectId
        db.announcements.delete_one({'_id': ObjectId(ann_id)})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def log_notification(title, message, type='info', role_target='admin'):
    try:
        db.notifications.insert_one({
            'title': title,
            'message': message,
            'type': type,
            'role_target': role_target,
            'read_by': [],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        print(f"Failed to log notification: {e}")

@app.route('/api/notifications')
def get_notifications():
    if not session.get('logged_in'):
        return jsonify([])
    role = session.get('role', 'student')
    user_id = session.get('user_id')
    
    target_roles = [role, 'all']
    if role == 'admin':
        target_roles.extend(['teacher', 'student'])
        
    notifs = list(db.notifications.find({
        'role_target': {'$in': target_roles},
        'read_by': {'$ne': user_id},
        'type': {'$ne': 'error'}
    }).sort('timestamp', -1).limit(10))
    
    # Fallback to hide old notifications that were globally marked 'read': True
    notifs = [n for n in notifs if not n.get('read', False)]
    
    for n in notifs:
        n['_id'] = str(n['_id'])
    return jsonify(notifs)

@app.route('/api/notifications/read/<notif_id>', methods=['POST'])
def mark_notification_read(notif_id):
    if not session.get('logged_in'):
        return jsonify({'success': False}), 401
    try:
        from bson.objectid import ObjectId
        user_id = str(session.get('user_id'))
        db.notifications.update_one(
            {'_id': ObjectId(notif_id)},
            {'$addToSet': {'read_by': user_id}}
        )
        return jsonify({'success': True})
    except:
        return jsonify({'success': False}), 500

@app.route('/api/notifications/clear_all', methods=['POST'])
def clear_all_notifications():
    if not session.get('logged_in'):
        return jsonify({'success': False}), 401
    try:
        user_id = str(session.get('user_id'))
        role = session.get('role', 'student')
        
        # Find all unread notifications for this user
        query = {
            'role_target': {'$in': [role, 'all']},
            'read_by': {'$ne': user_id},
            'type': {'$ne': 'error'}
        }
        
        # Add the user_id to read_by array for all matching documents
        db.notifications.update_many(
            query,
            {'$addToSet': {'read_by': user_id}}
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dev/wipe_users')
def dev_wipe_users():
    try:
        db.users.delete_many({})
        db.student_users.delete_many({})
        db.students.delete_many({})
        db.admins.delete_many({})
        return "SUCCESS: All user credentials, students, teachers, and admins have been completely removed. You can now start fresh!"
    except Exception as e:
        return f"Error wiping database: {str(e)}"



# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.office365.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
def refresh_mail_config():
    try:
        config_data = db.settings.find_one({}, {'_id': 0}) or {}
    except Exception:
        config_data = {}
    
    app.config['MAIL_USERNAME'] = config_data.get('MAIL_USERNAME') or 'agent4@indusschool.com'
    
    # Prioritize config_data, then env var, but override if env var looks like the old gmail app password (16 chars, lowercase)
    env_pw = os.environ.get('MAIL_PASSWORD')
    if env_pw and len(env_pw) == 16 and env_pw.islower():
        env_pw = None # Ignore likely old gmail app password
        
    app.config['MAIL_PASSWORD'] = config_data.get('MAIL_PASSWORD') or env_pw or 'Agent@2026'

refresh_mail_config()

mail = Mail(app)


def recalculate_students_attendance():
    students = list(db.students.find({}))
    attendance_data = list(db.attendance.find({}))
    
    for s in students:
        s_id = s.get('id')
        if not s_id:
            continue
        total_days = 0
        days_present = 0.0
        
        for att_doc in attendance_data:
            records = att_doc.get('records', {})
            if s_id in records:
                total_days += 1
                status = records[s_id]
                if status == 'Present':
                    days_present += 1.0
                elif status == 'Late':
                    days_present += 0.5
                # Absent counts as 0.0
                
        if total_days > 0:
            percentage = round((days_present / total_days) * 100, 1)
            if percentage.is_integer():
                percentage = int(percentage)
            db.students.update_one({'id': s_id}, {'$set': {'attendance': str(percentage)}})

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_otp_email(email, otp, is_reset=False):
    try:
        config_data = db.settings.find_one({}, {'_id': 0}) or {}
    except Exception:
        config_data = {}

    smtp_server = config_data.get('MAIL_SERVER', 'smtp.office365.com')
    smtp_port = int(config_data.get('MAIL_PORT', 587))
    smtp_user = config_data.get('MAIL_USERNAME', 'agent4@indusschool.com')
    smtp_pass = config_data.get('MAIL_PASSWORD', 'Agent@2026')

    subject = "Your OTP Code"
    body = f"Your OTP is: {otp}"
    print(f"\n--- [DEV] OTP for {email}: {otp} ---\n")
    
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = email

        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, email, msg.as_string())
        server.quit()
        print(f"Sent OTP email to {email}")
        return True
    except Exception as e:
        error_msg = str(e)
        print(f"Error sending email via SMTP: {error_msg}")
        return error_msg

@app.before_request
def update_last_active():
    if session.get('logged_in'):
        role = session.get('role')
        user_id = session.get('user_id')
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        try:
            if role == 'teacher':
                db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {'last_active': now_str}})
            elif role == 'student':
                db.student_users.update_one({'student_id': user_id}, {'$set': {'last_active': now_str}})
            elif role == 'admin':
                db.admins.update_one({'_id': ObjectId(user_id)}, {'$set': {'last_active': now_str}})
        except Exception as e:
            pass # Ignore malformed ObjectIds or DB errors

@app.route('/file/<file_id>')
def get_file(file_id):
    try:
        file = fs.get(ObjectId(file_id))
        return send_file(
            io.BytesIO(file.read()),
            mimetype=file.content_type,
            download_name=file.filename
        )
    except Exception as e:
        print(f"GridFS error: {e}")
        return "File not found", 404

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_type = request.form.get('login_type', 'teacher')
        email = request.form['email']
        
        if login_type == 'admin':
            if not db.admins.find_one({'email': 'kalmeshwargurav1028@gmail.com'}):
                db.admins.insert_one({
                    'email': 'kalmeshwargurav1028@gmail.com',
                    'password': 'Kalmeshwar@123',
                    'name': 'System Admin'
                })
                
            admin = db.admins.find_one({'email': email})
            password = request.form.get('password', '')
            if admin and (admin.get('password') == password or check_password_hash(admin.get('password', ''), password)):
                session['logged_in'] = True
                session['role'] = 'admin'
                session['user_id'] = str(admin['_id'])
                session['username'] = admin.get('name', 'Admin')
                session['email'] = email
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials. Please try again.')
                
        elif login_type == 'student':
            student_id_or_password = request.form.get('student_id')
            
            # Check new student_users auth collection first
            auth_user = db.student_users.find_one({'email': email})
            
            if auth_user and auth_user.get('password') == student_id_or_password:
                student_id = auth_user.get('student_id')
                session['logged_in'] = True
                session['role'] = 'student'
                session['user_id'] = student_id
                session['email'] = email
                # Get name from profile if available
                profile = db.students.find_one({'id': student_id})
                session['username'] = profile.get('name') if profile else email.split('@')[0]
                return redirect(url_for('student_profile', student_id=student_id))
            
            # Fallback to checking the students profile collection for older entries
            student = db.students.find_one({'email': email})
            
            if student and (student.get('password') == student_id_or_password or student.get('id') == student_id_or_password):
                student_id = student.get('id')
                session['logged_in'] = True
                session['role'] = 'student'
                session['user_id'] = student_id
                session['username'] = student.get('name', email.split('@')[0])
                session['email'] = email
                session['photo_url'] = student.get('photo_url', '')
                return redirect(url_for('student_profile', student_id=student_id))
            else:
                flash('Invalid student credentials. Please check your Email and Student ID.')
        else:
            password = request.form.get('password', '')
            user = db.users.find_one({'email': email})
            
            if user and (user['password'] == password or check_password_hash(user['password'], password)):
                if not user.get('verified'):
                    flash('This account is not verified yet. Please enter the verification code sent to your email.')
                    otp = generate_otp()
                    expiry = (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S.%f')
                    session['otp_code'] = otp
                    session['otp_expiry'] = expiry
                    session['otp_email'] = email
                    result = send_otp_email(email, otp)
                    if result is not True:
                        flash(f'Failed to send OTP email: {result}')
                    return redirect(url_for('verify_otp', email=email))
                    
                session['logged_in'] = True
                session['role'] = 'teacher'
                session['user_id'] = str(user['_id'])
                first = user.get('first_name') or ''
                last = user.get('last_name') or ''
                name = f"{first} {last}".strip()
                session['username'] = name if name else email.split('@')[0]
                session['email'] = email
                session['photo_url'] = user.get('photo_url')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid credentials. Please try again.')
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        signup_type = request.form.get('signup_type', 'teacher')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match. Please try again.')
            return render_template('signup.html')

        if signup_type == 'student':
            existing_student = db.student_users.find_one({'email': email})
            if existing_student:
                flash('Student with this email already exists. Please login.')
                return redirect(url_for('login'))
                
            # Create student
            all_students = list(db.students.find({}, {'id': 1, '_id': 0}))
            ind_ids = [s.get('id', '') for s in all_students if str(s.get('id', '')).startswith('IND')]
            max_num = 0
            for sid in ind_ids:
                try:
                    num = int(sid[3:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
            new_id = f"IND{max_num + 1:03d}"
            
            
            # Create auth entry
            db.student_users.insert_one({
                'student_id': new_id,
                'email': email,
                'password': password
            })
            
            # Create profile entry
            db.students.insert_one({
                'id': new_id,
                'name': f"{first_name} {last_name}".strip(),
                'email': email,
                'attendance': '100',
                'performance': '0',
            })
            flash(f'Student account created successfully! Your Student ID is {new_id}. You can now log in.')
            return redirect(url_for('login'))
            
        # Teacher signup flow below
            
        existing_user = db.users.find_one({'email': email})
        
        if existing_user:
            if existing_user.get('verified'):
                flash('Email already exists. Please login.')
                return redirect(url_for('login'))
            else:
                db.users.delete_one({'email': email})
                
        otp = generate_otp()
        expiry = (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S.%f')
        db.users.insert_one({
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': password,
            'verified': False
        })
        
        session['otp_code'] = otp
        session['otp_expiry'] = expiry
        session['otp_email'] = email
        result = send_otp_email(email, otp)
        
        if result is True:
            flash('Verification code sent to your email! Please verify below.')
        else:
            flash(f'Failed to send verification code email: {result}')
        return redirect(url_for('verify_otp', email=email))
        
    return render_template('signup.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    email = request.args.get('email') or request.form.get('email')
    if request.method == 'POST':
        otp = request.form.get('otp')
        
        session_otp = session.get('otp_code')
        session_email = session.get('otp_email')
        expiry_str = session.get('otp_expiry')
        
        if session_otp and session_otp == otp and session_email == email:
            if expiry_str and datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S.%f') > datetime.now():
                db.users.update_one({'email': email}, {'$set': {'verified': True}})
                session.pop('otp_code', None)
                session.pop('otp_email', None)
                session.pop('otp_expiry', None)
                
                user = db.users.find_one({'email': email})
                if user:
                    session['logged_in'] = True
                    session['user_id'] = str(user['_id'])
                    first = user.get('first_name') or ''
                    last = user.get('last_name') or ''
                    name = f"{first} {last}".strip()
                    session['username'] = name if name else email.split('@')[0]
                    session['email'] = email
                    flash('Verified and logged in successfully!')
                    return redirect(url_for('dashboard'))
                else:
                    flash('User not found.')
                    return redirect(url_for('login'))
            else:
                flash('OTP has expired. Please try again.')
        else:
            flash('Incorrect verification code or invalid session.')
            
    return render_template('verify_otp.html', email=email)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = db.users.find_one({'email': email})
        student = db.student_users.find_one({'email': email}) or db.students.find_one({'email': email})
        
        if (user and user.get('verified')) or student:
            otp = generate_otp()
            expiry = (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S.%f')
            session['otp_code'] = otp
            session['otp_expiry'] = expiry
            session['otp_email'] = email
            result = send_otp_email(email, otp, is_reset=True)
            if result is True:
                flash('Reset code sent to your email.')
            else:
                flash(f'Failed to send reset code email: {result}')
            return redirect(url_for('reset_password', email=email))
        else:
            flash('Email not found or not verified.')
            
    return render_template('forgot_password.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email') or request.form.get('email')
    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        session_otp = session.get('otp_code')
        session_email = session.get('otp_email')
        expiry_str = session.get('otp_expiry')
        
        if new_password != confirm_password:
            flash('Passwords do not match.')
            return render_template('reset_password.html', email=email)
            
        if session_otp and session_otp == otp and session_email == email:
            if expiry_str and datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S.%f') > datetime.now():
                user = db.users.find_one({'email': email})
                student = db.student_users.find_one({'email': email})
                student_profile = db.students.find_one({'email': email})
                
                if user:
                    db.users.update_one({'email': email}, {'$set': {'password': new_password}})
                if student:
                    db.student_users.update_one({'email': email}, {'$set': {'password': new_password}})
                if student_profile:
                    db.students.update_one({'email': email}, {'$set': {'password': new_password}})
                    
                session.pop('otp_code', None)
                session.pop('otp_email', None)
                session.pop('otp_expiry', None)
                
                flash('Password changed successfully! You can now log in.')
                return redirect(url_for('login'))
            else:
                flash('OTP has expired. Please try again.')
        else:
            flash('Incorrect verification code.')
            
    return render_template('reset_password.html', email=email)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('role') == 'student':
        return redirect(url_for('student_profile', student_id=session.get('user_id')))
    
    students = list(db.students.find({}, {'_id': 0}))
    
    # Analytics Calculations
    total_students = len(students)
    
    # Board Distribution
    board_counts = {}
    
    # Attendance Present/Absent (based on % >= 75 is Present)
    present_count = 0
    absent_count = 0
    
    # Monthly Trends (Mock data)
    monthly_attendance = [85, 88, 82, 86, 90, 89, 92, 95, 88, 85, 87, 90]
    
    class_distribution = {}
    
    performance_sum = 0
    attendance_sum = 0
    
    for s in students:
        # Boards
        board = s.get('board', 'Unknown')
        board_counts[board] = board_counts.get(board, 0) + 1
        
        # Classes
        student_class = s.get('student_class', '10th')
        class_distribution[student_class] = class_distribution.get(student_class, 0) + 1
        
        # Attendance & Performance
        att = float(s.get('attendance', 0))
        perf = float(s.get('performance', 0))
        attendance_sum += att
        performance_sum += perf
        
        if att >= 75:
            present_count += 1
        else:
            absent_count += 1
            
    avg_attendance = round(attendance_sum / total_students, 1) if total_students > 0 else 0
    avg_performance = round(performance_sum / total_students, 1) if total_students > 0 else 0
    
    analytics = {
        'total_students': total_students,
        'avg_attendance': avg_attendance,
        'avg_performance': avg_performance,
        'present_count': present_count,
        'absent_count': absent_count,
        'board_labels': list(board_counts.keys()),
        'board_data': list(board_counts.values()),
        'class_labels': list(class_distribution.keys()),
        'class_data': list(class_distribution.values()),
        'monthly_attendance': monthly_attendance
    }
    
    return render_template('dashboard.html', students=students, analytics=analytics)

@app.route('/student/<student_id>')
def student_profile(student_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    student = db.students.find_one({'id': student_id}, {'_id': 0})
    
    if not student:
        flash('Student not found.')
        return redirect(url_for('dashboard'))
        
    # Generate mock data for arrays if missing
    if 'marks' not in student:
        student['marks'] = [
            {'subject': 'Math', 'score': random.randint(60, 100)},
            {'subject': 'Science', 'score': random.randint(60, 100)},
            {'subject': 'English', 'score': random.randint(60, 100)},
            {'subject': 'History', 'score': random.randint(60, 100)},
            {'subject': 'Computer', 'score': random.randint(60, 100)}
        ]
    if 'attendance_history' not in student:
        student['attendance_history'] = [
            {'month': 'Jan', 'days_present': random.randint(15, 22), 'total_days': 22},
            {'month': 'Feb', 'days_present': random.randint(15, 20), 'total_days': 20},
            {'month': 'Mar', 'days_present': random.randint(15, 22), 'total_days': 22},
            {'month': 'Apr', 'days_present': random.randint(15, 21), 'total_days': 21}
        ]
        
    # Fetch teachers for the Contact Directory
    teachers = list(db.users.find({'role': 'teacher'}, {'password': 0}))
    for t in teachers:
        t['_id'] = str(t['_id'])
        if 'first_name' in t and 'last_name' in t:
            t['display_name'] = f"{t['first_name']} {t['last_name']}"
        else:
            t['display_name'] = t.get('email', 'Teacher').split('@')[0].capitalize()
        
    return render_template('student_profile.html', student=student, teachers=teachers)

@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    now = datetime.utcnow()
    active_threshold = now - timedelta(minutes=15)
    
    # Process admins
    admins = list(db.admins.find({}))
    active_admins = []
    inactive_admins = []
    for a in admins:
        last_active_str = a.get('last_active')
        a_data = {
            'id': str(a.get('_id')),
            'email': a.get('email'),
            'name': a.get('name', a.get('email').split('@')[0] if a.get('email') else 'Admin'),
            'last_active': last_active_str or 'Never'
        }
        if last_active_str:
            try:
                last_active = datetime.strptime(last_active_str, '%Y-%m-%d %H:%M:%S')
                if last_active >= active_threshold:
                    active_admins.append(a_data)
                else:
                    inactive_admins.append(a_data)
            except ValueError:
                inactive_admins.append(a_data)
        else:
            inactive_admins.append(a_data)

    # Process teachers
    teachers = list(db.users.find({}))
    active_teachers = []
    inactive_teachers = []
    for t in teachers:
        last_active_str = t.get('last_active')
        t_data = {
            'id': str(t.get('_id')),
            'email': t.get('email'),
            'name': f"{t.get('first_name', '')} {t.get('last_name', '')}".strip() or t.get('email').split('@')[0],
            'last_active': last_active_str or 'Never'
        }
        if last_active_str:
            try:
                last_active = datetime.strptime(last_active_str, '%Y-%m-%d %H:%M:%S')
                if last_active >= active_threshold:
                    active_teachers.append(t_data)
                else:
                    inactive_teachers.append(t_data)
            except ValueError:
                inactive_teachers.append(t_data)
        else:
            inactive_teachers.append(t_data)
            
    # Process students
    student_users = list(db.student_users.find({}))
    student_profiles = {s['id']: s for s in db.students.find({}, {'_id': 0})}
    
    active_students = []
    inactive_students = []
    for s in student_users:
        last_active_str = s.get('last_active')
        profile = student_profiles.get(s.get('student_id'), {})
        s_data = {
            'id': str(s.get('_id')),
            'email': s.get('email'),
            'student_id': s.get('student_id'),
            'name': profile.get('name', s.get('email')),
            'last_active': last_active_str or 'Never'
        }
        
        if last_active_str:
            try:
                last_active = datetime.strptime(last_active_str, '%Y-%m-%d %H:%M:%S')
                if last_active >= active_threshold:
                    active_students.append(s_data)
                else:
                    inactive_students.append(s_data)
            except ValueError:
                inactive_students.append(s_data)
        else:
            inactive_students.append(s_data)
            
    try:
        pipeline = [{'$group': {'_id': None, 'total_size': {'$sum': '$length'}}}]
        result = list(db.fs.files.aggregate(pipeline))
        total_bytes = result[0]['total_size'] if result else 0
        storage_mb = total_bytes / (1024 * 1024)
        storage_gb = storage_mb / 1024
        storage_used_str = f"{storage_gb:.2f} GB" if storage_gb >= 1 else f"{storage_mb:.2f} MB"
        storage_percentage = min(100, (storage_gb / 100) * 100)
    except Exception:
        storage_used_str = "0 MB"
        storage_percentage = 0

    system_errors = db.notifications.count_documents({'type': 'error', 'read': False})

    stats = {
        'total_admins': len(admins),
        'active_admins': len(active_admins),
        'total_teachers': len(teachers),
        'active_teachers': len(active_teachers),
        'total_students': len(student_users),
        'active_students': len(active_students),
        'system_errors': system_errors,
        'storage_used_str': storage_used_str,
        'storage_percentage': storage_percentage,
        'pending_approvals': 0
    }
    
    # Fetch all materials
    materials = list(db.materials.find().sort('uploaded_at', -1))
    
    # Fetch all announcements
    announcements = list(db.announcements.find().sort('date_sent', -1))
    now_time = datetime.now().strftime('%Y-%m-%d')
    
    # Fetch role permissions
    global_config = db.role_permissions.find_one({'_id': 'global_config'}) or {}
    if not global_config.get('teacher'):
        global_config['teacher'] = {'view_dashboard': True, 'manage_students': True, 'edit_materials': True, 'modify_attendance': True}
    if not global_config.get('student'):
        global_config['student'] = {'view_dashboard': True}
    
    return render_template('admin_dashboard.html', stats=stats, active_admins=active_admins, inactive_admins=inactive_admins, active_teachers=active_teachers, inactive_teachers=inactive_teachers, active_students=active_students, inactive_students=inactive_students, materials=materials, announcements=announcements, now_time=now_time, global_config=global_config)

@app.route('/super_admin_profile')
def super_admin_profile():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    admin = db.admins.find_one({'_id': ObjectId(session.get('user_id'))})
    if not admin:
        admin = db.users.find_one({'_id': ObjectId(session.get('user_id'))})
        
    return render_template('admin_profile.html', admin=admin or {})

@app.route('/super_admin_update_profile', methods=['POST'])
def super_admin_update_profile():
    if not session.get('logged_in') or session.get('role') not in ['admin', 'teacher']:
        return jsonify({'success': False}), 403
        
    phone = request.form.get('phone')
    department = request.form.get('department')
    
    schools = request.form.get('schools')
    grades = request.form.get('grades')
    
    update_fields = {'phone': phone, 'department': department}
    if schools:
        import json
        try:
            update_fields['schools'] = json.loads(schools)
        except:
            pass
    if grades:
        import json
        try:
            update_fields['grades'] = json.loads(grades)
        except:
            pass
    
    result = db.admins.update_one(
        {'_id': ObjectId(session.get('user_id'))},
        {'$set': update_fields}
    )
    if result.matched_count == 0:
        db.users.update_one(
            {'_id': ObjectId(session.get('user_id'))},
            {'$set': update_fields}
        )
    return jsonify({'success': True})

@app.route('/admin/reset_password', methods=['POST'])
def admin_reset_password():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    user_type = request.form.get('user_type') # 'teacher' or 'student'
    user_id = request.form.get('user_id')
    new_password = request.form.get('new_password')
    
    if not all([user_type, user_id, new_password]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
    hashed_password = generate_password_hash(new_password)
    
    try:
        if user_type == 'teacher':
            result = db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'password': hashed_password}}
            )
        elif user_type == 'student':
            result = db.student_users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'password': hashed_password}}
            )
        else:
            return jsonify({'success': False, 'error': 'Invalid user type'}), 400
            
        if result.modified_count == 1:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'User not found or password already identical'}), 200
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/timetable')
def timetable():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    # Generate mock timetable data
    timetable_data = {
        'Monday': [
            {'time': '09:00 AM', 'subject': 'Mathematics', 'room': 'Room 101', 'teacher': 'Mr. Smith'},
            {'time': '10:30 AM', 'subject': 'Physics', 'room': 'Lab 3', 'teacher': 'Dr. Brown'},
            {'time': '01:00 PM', 'subject': 'Computer Science', 'room': 'Lab 1', 'teacher': 'Mrs. Davis'}
        ],
        'Tuesday': [
            {'time': '09:00 AM', 'subject': 'Chemistry', 'room': 'Lab 2', 'teacher': 'Dr. Wilson'},
            {'time': '11:00 AM', 'subject': 'English Literature', 'room': 'Room 205', 'teacher': 'Ms. Taylor'}
        ],
        'Wednesday': [
            {'time': '09:00 AM', 'subject': 'Mathematics', 'room': 'Room 101', 'teacher': 'Mr. Smith'},
            {'time': '10:30 AM', 'subject': 'History', 'room': 'Room 302', 'teacher': 'Mr. Clark'},
            {'time': '02:00 PM', 'subject': 'Physical Education', 'room': 'Gym', 'teacher': 'Coach Miller'}
        ],
        'Thursday': [
            {'time': '09:30 AM', 'subject': 'Physics', 'room': 'Lab 3', 'teacher': 'Dr. Brown'},
            {'time': '11:30 AM', 'subject': 'Computer Science', 'room': 'Lab 1', 'teacher': 'Mrs. Davis'}
        ],
        'Friday': [
            {'time': '09:00 AM', 'subject': 'Biology', 'room': 'Lab 4', 'teacher': 'Dr. Evans'},
            {'time': '11:00 AM', 'subject': 'Art', 'room': 'Studio 1', 'teacher': 'Ms. White'},
            {'time': '01:30 PM', 'subject': 'English Literature', 'room': 'Room 205', 'teacher': 'Ms. Taylor'}
        ]
    }
    
    # Get current day of week to highlight it
    current_day = datetime.now().strftime('%A')
    
    return render_template('student_timetable.html', timetable=timetable_data, current_day=current_day)

@app.route('/assignments')
def assignments():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    # Generate mock assignments data
    now = datetime.now()
    assignments_data = [
        {
            'id': 1,
            'title': 'Calculus Final Project',
            'subject': 'Mathematics',
            'due_date': (now + timedelta(days=2)).strftime('%Y-%m-%d %H:%M'),
            'days_left': 2,
            'status': 'pending',
            'type': 'Project'
        },
        {
            'id': 2,
            'title': 'Quantum Mechanics Essay',
            'subject': 'Physics',
            'due_date': (now + timedelta(days=5)).strftime('%Y-%m-%d %H:%M'),
            'days_left': 5,
            'status': 'pending',
            'type': 'Homework'
        },
        {
            'id': 3,
            'title': 'Data Structures Implementation',
            'subject': 'Computer Science',
            'due_date': (now + timedelta(days=1)).strftime('%Y-%m-%d %H:%M'),
            'days_left': 1,
            'status': 'urgent',
            'type': 'Lab Work'
        },
        {
            'id': 4,
            'title': 'World War II Analysis',
            'subject': 'History',
            'due_date': (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M'),
            'days_left': -1,
            'status': 'submitted',
            'type': 'Essay'
        }
    ]
    
    return render_template('student_assignments.html', assignments=assignments_data)

@app.route('/student/materials')
def student_materials():
    if not session.get('logged_in') or session.get('role') != 'student':
        return redirect(url_for('login'))
        
    student_id = session.get('user_id')
    student = db.students.find_one({'id': student_id}, {'_id': 0})
    if not student:
        return redirect(url_for('login'))
        
    student_class = student.get('student_class')
    materials = []
    if student_class:
        materials = list(db.materials.find({'class': student_class}).sort('uploaded_at', -1))
        
    return render_template('student_materials.html', student=student, materials=materials)

@app.route('/student/<student_id>/id_card')
def student_id_card(student_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    student = db.students.find_one({'id': student_id}, {'_id': 0})
    
    if not student:
        flash('Student not found.')
        return redirect(url_for('dashboard'))
        
    return render_template('id_card.html', student=student)

@app.route('/admin_profile', methods=['GET', 'POST'])
def admin_profile():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('role') == 'student':
        return redirect(url_for('student_profile', student_id=session.get('user_id')))
        
    user_id = session.get('user_id')
    from bson.objectid import ObjectId
    user = db.users.find_one({'_id': ObjectId(user_id)})
    collection = db.users
    if not user:
        user = db.admins.find_one({'_id': ObjectId(user_id)})
        collection = db.admins
        
    if not user:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        bio = request.form.get('bio')
        
        photo = request.files.get('photo')
        photo_url = user.get('photo_url', '') if user else ''
        if photo and photo.filename != '':
            filename = secure_filename(photo.filename)
            unique_filename = f"admin_{uuid.uuid4().hex[:8]}_{filename}"
            # Save directly to GridFS
            file_id = fs.put(photo, filename=unique_filename, content_type=photo.content_type)
            photo_url = url_for('get_file', file_id=str(file_id))
        collection.update_one({'_id': ObjectId(user_id)}, {'$set': {
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'bio': bio,
            'photo_url': photo_url
        }})
        
        # Update session variables
        name = f"{first_name} {last_name}".strip()
        session['username'] = name if name else user.get('email', '').split('@')[0]
        session['photo_url'] = photo_url
        
        flash('Admin profile updated successfully!')
        return redirect(url_for('admin_profile'))
        
    return render_template('admin_profile.html', admin=user)

@app.route('/profile', methods=['GET', 'POST'])
def profile_form():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('role') == 'student':
        return redirect(url_for('student_profile', student_id=session.get('user_id')))
        
    student_id = request.args.get('id')
    student = db.students.find_one({'id': student_id}, {'_id': 0}) if student_id else None

    if request.method == 'POST':
        name = request.form.get('name')
        dob = request.form.get('dob')
        age = request.form.get('age')
        gender = request.form.get('gender')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        blood_group = request.form.get('blood_group')
        
        board = request.form.get('board')
        student_class = request.form.get('student_class', '10th')
        division = request.form.get('division', 'A')
        academic_year = request.form.get('academic_year')
        roll_number = request.form.get('roll_number')
        
        parent_name = request.form.get('parent_name')
        relationship = request.form.get('relationship')
        parent_phone = request.form.get('parent_phone')
        parent_email = request.form.get('parent_email')
        occupation = request.form.get('occupation')
        
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        pincode = request.form.get('pincode')
        
        subject_names = request.form.getlist('subject_names[]')
        subject_scores = request.form.getlist('subject_scores[]')
        subjects = {}
        for s_name, s_score in zip(subject_names, subject_scores):
            if s_name.strip():
                subjects[s_name.strip()] = s_score.strip()
        
        photo = request.files.get('photo')
        photo_url = student.get('photo_url', '') if student else ''
        if photo and photo.filename != '':
            filename = secure_filename(photo.filename)
            unique_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
            # Save directly to GridFS
            file_id = fs.put(photo, filename=unique_filename, content_type=photo.content_type)
            photo_url = url_for('get_file', file_id=str(file_id))
            
        if student:
            # Update existing
            db.students.update_one({'id': student_id}, {'$set': {
                'name': name, 'dob': dob, 'age': age, 'gender': gender, 'blood_group': blood_group,
                'email': email, 'phone': phone,
                'board': board, 'student_class': student_class, 'division': division,
                'academic_year': academic_year, 'roll_number': roll_number,
                'parent_name': parent_name, 'relationship': relationship,
                'parent_phone': parent_phone, 'parent_email': parent_email,
                'occupation': occupation, 'address': address, 'city': city,
                'state': state, 'pincode': pincode, 'photo_url': photo_url,
                'subjects': subjects,
                'password': password if password else student.get('password', '')
            }})
            
            # Update or create auth entry
            if password or email != student.get('email'):
                auth_user = db.student_users.find_one({'student_id': student_id})
                if auth_user:
                    update_data = {}
                    if email: update_data['email'] = email
                    if password: update_data['password'] = password
                    if update_data:
                        db.student_users.update_one({'student_id': student_id}, {'$set': update_data})
                elif password:
                    db.student_users.insert_one({
                        'student_id': student_id,
                        'email': email,
                        'password': password
                    })
        else:
            # Create new
            all_students = list(db.students.find({}, {'id': 1, '_id': 0}))
            ind_ids = [s.get('id', '') for s in all_students if str(s.get('id', '')).startswith('IND')]
            max_num = 0
            for sid in ind_ids:
                try:
                    num = int(sid[3:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
            new_id = f"IND{max_num + 1:03d}"
            
            new_student = {
                'id': new_id,
                'name': name, 'dob': dob, 'age': age, 'gender': gender, 'blood_group': blood_group,
                'email': email, 'phone': phone,
                'board': board, 'student_class': student_class, 'division': division,
                'academic_year': academic_year, 'roll_number': roll_number,
                'parent_name': parent_name, 'relationship': relationship,
                'parent_phone': parent_phone, 'parent_email': parent_email,
                'occupation': occupation, 'address': address, 'city': city,
                'state': state, 'pincode': pincode, 'photo_url': photo_url,
                'attendance': '100', 'performance': '80',
                'subjects': subjects,
                'password': password
            }
            db.students.insert_one(new_student)
            
            # Create auth entry if password provided
            if password:
                db.student_users.insert_one({
                    'student_id': new_id,
                    'email': email,
                    'password': password
                })
            
        flash('Student record saved successfully!')
        return redirect(url_for('dashboard'))

    return render_template('profile_form.html', student=student)

@app.route('/delete/<student_id>', methods=['POST'])
def delete_student(student_id):
    if not session.get('logged_in') or session.get('role') == 'student':
        return redirect(url_for('login'))
        
    db.students.delete_one({'id': student_id})
    flash('Student deleted successfully.')
    return redirect(url_for('dashboard'))

@app.route('/quick_add_mark/<student_id>', methods=['POST'])
def quick_add_mark(student_id):
    if not session.get('logged_in') or session.get('role') == 'student':
        return redirect(url_for('login'))
        
    subject = request.form.get('subject')
    score = request.form.get('score')
    
    if subject and score:
        db.students.update_one(
            {'id': student_id},
            {'$set': {f'subjects.{subject.strip()}': score.strip()}}
        )
        flash(f'Mark added successfully for {subject}!')
        
    return redirect(url_for('student_profile', student_id=student_id))

@app.route('/api/analyze_student/<student_id>', methods=['POST'])
def analyze_student(student_id):
    if not session.get('logged_in'):
        return {'error': 'Unauthorized'}, 401
        
    student = db.students.find_one({'id': student_id}, {'_id': 0})
    
    if not student:
        return {'error': 'Student not found'}, 404
        
    data = request.get_json()
    message = data.get('message', '').strip()
    
    performance = float(student.get('performance', 0))
    attendance = float(student.get('attendance', 0))
    name = student.get('name', 'This student')
    
    client, api_key = configure_gemini()
    if not api_key:
        return {'response': f"Hi, I am your AI Mentor! Please set GEMINI_API_KEY in Settings to enable real AI capabilities. Profile: {name} (Score: {performance}, Attendance: {attendance}%)."}

    try:
        system_prompt = f"""You are the "Dashboard AI Mentor," an elite student data analyst integrated directly into the Indus Portal. Your core purpose is to parse student metrics, attendance patterns, and overall academic performance to deliver lightning-fast, high-impact suggestions to educators.
Follow these absolute operational constraints:
1. Contextual Relevance: Assume every query relates directly to student health, performance, or portal analytics.
2. Brutal Conciseness: You live in a compact UI chat box. Never use conversational introductions like "Sure, I can look into that." Get straight to the data points.
3. Length Limit: Cap every response at a maximum of 3 sentences. If code is requested, provide only minimal, un-bloated snippets.
4. Tone: Highly professional, encouraging, analytical, and authoritative.
Student Data: {name} | Performance={performance}/100 | Attendance={attendance}%."""
        
        if message.lower() in ['', 'initial', 'analyze']:
            prompt = f"{system_prompt}\n\nPlease provide a brief initial analysis of {name} and suggest one area to focus on."
        else:
            prompt = f"{system_prompt}\n\nThe teacher asks: {message}"

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        response_text = response.text.replace('*', '')
        return {'response': response_text}
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return {'response': "Sorry, I encountered an error communicating with my AI brain."}

@app.route('/api/dashboard_ai', methods=['POST'])
def dashboard_ai():
    if not session.get('logged_in'):
        return {'error': 'Unauthorized'}, 401
        
    students = list(db.students.find({}, {'_id': 0}))
    data = request.get_json()
    message = data.get('message', '').strip()
    
    total = len(students)
    present = sum(1 for s in students if float(s.get('attendance', 0)) >= 75)
    absent = total - present
    avg_perf = round(sum(float(s.get('performance', 0)) for s in students) / total, 1) if total > 0 else 0
    
    client, api_key = configure_gemini()
    if not api_key:
        return {'response': f"Hello! I am your Dashboard AI Assistant. Please set GEMINI_API_KEY in Settings. Roster: {total} students, Avg Perf: {avg_perf}."}
        
    try:
        low_att_list = []
        high_perf_list = []
        for s in students:
            name = s.get('name', 'Unknown')
            perf = float(s.get('performance', 0))
            att = float(s.get('attendance', 0))
            if att < 75:
                low_att_list.append(f"{name} ({int(att)}%)")
            if perf >= 90:
                high_perf_list.append(f"{name} ({int(perf)} total)")
                
        low_att_str = ", ".join(low_att_list) if low_att_list else "None"
        high_perf_str = ", ".join(high_perf_list) if high_perf_list else "None"
        
        system_prompt = f"""You are the "Dashboard AI Mentor," an elite student data analyst integrated directly into the Indus Portal. Your core purpose is to parse student metrics, attendance patterns, and overall academic performance to deliver lightning-fast, high-impact suggestions to educators.
Follow these absolute operational constraints:
1. Contextual Relevance: Assume every query relates directly to student health, performance, or portal analytics.
2. Brutal Conciseness: You live in a compact UI chat box. Never use conversational introductions like "Sure, I can look into that." Get straight to the data points.
3. Length Limit: Cap every response at a maximum of 3 sentences. If code is requested, provide only minimal, un-bloated snippets.
4. Tone: Highly professional, encouraging, analytical, and authoritative.
Data: Total Students={total}, Low Attendance (<75%)={low_att_str}, High Performers={high_perf_str}."""

        if message.lower() in ['', 'initial']:
            prompt = f"{system_prompt}\nGive 3 actionable bullet points for the teacher."
        else:
            prompt = f"{system_prompt}\nThe teacher asks: {message}"

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        response_text = response.text.replace('*', '')
        return {'response': response_text}
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return {'response': "Sorry, I encountered an error communicating with my AI brain."}

@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('role') == 'student':
        return redirect(url_for('student_profile', student_id=session.get('user_id')))
        
    selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d')) or datetime.now().strftime('%Y-%m-%d')
    students = list(db.students.find({}, {'_id': 0}))
    
    if request.method == 'POST':
        new_records = {}
        for s in students:
            s_id = s['id']
            status = request.form.get(f'status_{s_id}')
            if status in ['Present', 'Absent', 'Late']:
                new_records[s_id] = status
            else:
                new_records[s_id] = 'Present'
                
        db.attendance.update_one(
            {'date': selected_date},
            {'$set': {'records': new_records}},
            upsert=True
        )
        
        # Trigger recalculation
        recalculate_students_attendance()
        
        # Check for alerts
        updated_students = list(db.students.find({}, {'_id': 0}))
        for s in updated_students:
            status_today = new_records.get(s['id'], 'Present')
            att_percentage = float(s.get('attendance', 100))
            
            if att_percentage < 75 and status_today == 'Absent':
                name = s.get('name', 'Student')
                msg = f"Alert: {name}'s attendance has dropped to {att_percentage}%. Please ensure they attend classes regularly."
                
                phone = s.get('parent_phone') or s.get('phone')
                email = s.get('parent_email') or s.get('email')
                
                if phone:
                    send_twilio_sms(phone, msg)
                elif email:
                    send_sendgrid_email(email, "Low Attendance Alert", msg)
        
        flash(f'Attendance for {selected_date} has been saved successfully!')
        
        flash('Attendance updated successfully!')
        return redirect(url_for('attendance', date=selected_date))
        
    # GET request
    daily_doc = db.attendance.find_one({'date': selected_date})
    daily_records = daily_doc.get('records', {}) if daily_doc else {}
    
    all_docs = list(db.attendance.find({}, {'date': 1, '_id': 0}))
    all_dates = sorted([doc.get('date') for doc in all_docs if doc.get('date')], reverse=True)
    
    total_count = len(students)
    present_count = 0
    absent_count = 0
    late_count = 0
    
    for s in students:
        status = daily_records.get(s['id'])
        if status == 'Present':
            present_count += 1
        elif status == 'Absent':
            absent_count += 1
        elif status == 'Late':
            late_count += 1
            
    stats = {
        'total': total_count,
        'present': present_count,
        'absent': absent_count,
        'late': late_count,
        'ratio': round((present_count + late_count) / total_count * 100, 1) if total_count > 0 and len(daily_records) > 0 else 0
    }
    
    return render_template(
        'attendance.html',
        students=students,
        selected_date=selected_date,
        daily_records=daily_records,
        all_dates=all_dates,
        stats=stats
    )

@app.route('/materials', methods=['GET', 'POST'])
def materials():
    if not session.get('logged_in') or session.get('role') == 'student':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        student_class = request.form.get('student_class')
        subject = request.form.get('subject')
        file = request.files.get('file')
        
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
            
            # Save directly to GridFS
            file_id = fs.put(file, filename=unique_filename, content_type=file.content_type)
            file_url = url_for('get_file', file_id=str(file_id))
            
            # Save to db
            db.materials.insert_one({
                'title': title,
                'class': student_class,
                'subject': subject,
                'file_url': file_url,
                'uploaded_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'teacher_id': session.get('user_id')
            })
            
            # Email Notification
            students_in_class = list(db.students.find({'student_class': student_class}))
            if students_in_class:
                refresh_mail_config()
                emails_sent = 0
                for st in students_in_class:
                    if st.get('email'):
                        try:
                            msg = Message(
                                f"New Study Material: {title}",
                                sender=app.config.get('MAIL_USERNAME'),
                                recipients=[st['email']]
                            )
                            login_url = url_for('login', _external=True)
                            msg.body = f"Hello {st.get('name', 'Student')},\n\nNew study material '{title}' for {subject} has been uploaded by your teacher.\n\nPlease log in to your Student Portal to view it: {login_url}\n\nRegards,\nIndus Portal"
                            mail.send(msg)
                            emails_sent += 1
                        except Exception as e:
                            print(f"Failed to send email to {st['email']}: {e}")
                
                flash(f'Material uploaded and {emails_sent} students notified!')
            else:
                flash('Material uploaded successfully! No students found in this class to notify.')
                
            return redirect(url_for('materials'))
            
    all_materials = list(db.materials.find().sort('uploaded_at', -1))
    return render_template('materials.html', materials=all_materials)

@app.route('/reports')
def reports():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('role') == 'student':
        return redirect(url_for('student_profile', student_id=session.get('user_id')))
        
    students = list(db.students.find({}, {'_id': 0}))
    
    total_students = len(students)
    board_counts = {}
    class_distribution = {}
    class_performance_sum = {}
    class_student_count = {}
    subject_sums = {}
    subject_counts = {}
    all_subjects = set()
    
    for s in students:
        board = s.get('board', 'Unknown')
        board_counts[board] = board_counts.get(board, 0) + 1
        
        student_class = s.get('student_class', 'Unknown')
        class_distribution[student_class] = class_distribution.get(student_class, 0) + 1
        
        perf = float(s.get('performance', 0))
        class_performance_sum[student_class] = class_performance_sum.get(student_class, 0) + perf
        class_student_count[student_class] = class_student_count.get(student_class, 0) + 1
        
        subjects = s.get('subjects', {})
        for subject, score in subjects.items():
            if subject not in all_subjects:
                all_subjects.add(subject)
            try:
                val = float(score)
                subject_sums[subject] = subject_sums.get(subject, 0) + val
                subject_counts[subject] = subject_counts.get(subject, 0) + 1
            except (ValueError, TypeError):
                pass
                
    all_subjects_sorted = sorted(list(all_subjects))
            
    avg_performance_by_class = {}
    for cls, total_perf in class_performance_sum.items():
        count = class_student_count[cls]
        avg_performance_by_class[cls] = round(total_perf / count, 1) if count > 0 else 0
        
    avg_subjects = {}
    for subject, total_score in subject_sums.items():
        count = subject_counts[subject]
        avg_subjects[subject] = round(total_score / count, 1) if count > 0 else 0
        
    analytics = {
        'total_students': total_students,
        'board_labels': list(board_counts.keys()),
        'board_data': list(board_counts.values()),
        'class_perf_labels': list(avg_performance_by_class.keys()),
        'class_perf_data': list(avg_performance_by_class.values()),
        'subject_labels': list(avg_subjects.keys()),
        'subject_data': list(avg_subjects.values())
    }
    
    # Save the generated report to MongoDB
    db.reports.update_one(
        {'type': 'latest_analytics'},
        {'$set': {'generated_at': datetime.now(), 'analytics': analytics, 'students_count': total_students}},
        upsert=True
    )
    
    return render_template('reports.html', students=students, analytics=analytics, all_subjects=all_subjects_sorted)

@app.route('/ai_box')
def ai_box():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('ai_box.html')

@app.route('/export_students')
def export_students():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    student_class = request.args.get('class', '')
    
    query = {}
    if student_class:
        query['student_class'] = student_class
        
    students = list(db.students.find(query, {'_id': 0}))
        
    output = io.StringIO()
    fieldnames = ['id', 'name', 'dob', 'gender', 'board', 'student_class', 'division', 'academic_year', 'roll_number', 'parent_name', 'relationship', 'parent_phone', 'parent_email', 'occupation']
    
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for student in students:
        writer.writerow(student)
        
    output.seek(0)
    response = Response(output.getvalue(), mimetype='text/csv')
    
    filename = f"students_class_{student_class}.csv" if student_class else "all_students.csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

@app.route('/import_students', methods=['POST'])
def import_students():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    target_class = request.form.get('target_class', '')
    csv_file = request.files.get('csv_file')
    
    if not csv_file or csv_file.filename == '':
        flash('No file selected for import.')
        return redirect(url_for('dashboard'))
        
    try:
        stream = io.StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        all_students = list(db.students.find({}, {'id': 1, '_id': 0}))
        imported_count = 0
        
        for row in csv_reader:
            ind_ids = [s.get('id', '') for s in all_students if str(s.get('id', '')).startswith('IND')]
            max_num = 0
            for sid in ind_ids:
                try:
                    num = int(sid[3:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
            new_id = f"IND{max_num + 1:03d}"
            
            new_student = {
                'id': new_id,
                'name': row.get('name', ''),
                'dob': row.get('dob', ''),
                'gender': row.get('gender', ''),
                'board': row.get('board', ''),
                'student_class': row.get('student_class') or target_class or '10th',
                'division': row.get('division', 'A'),
                'academic_year': row.get('academic_year', '2026'),
                'roll_number': row.get('roll_number', ''),
                'parent_name': row.get('parent_name', ''),
                'relationship': row.get('relationship', ''),
                'parent_phone': row.get('parent_phone', ''),
                'parent_email': row.get('parent_email', ''),
                'occupation': row.get('occupation', ''),
                'attendance': '100',
                'performance': '80'
            }
            db.students.insert_one(new_student)
            all_students.append({'id': new_id}) # Keep track for next iteration
            imported_count += 1
            
        flash(f'Successfully imported {imported_count} students.')
        
    except Exception as e:
        flash(f'Error importing CSV: {str(e)}')
        
    return redirect(url_for('dashboard'))





@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('role') == 'student':
        return redirect(url_for('student_profile', student_id=session.get('user_id')))
        
    config_data = db.settings.find_one({}, {'_id': 0}) or {}
    
    if request.method == 'POST':
        school_name = request.form.get('school_name')
        academic_year = request.form.get('academic_year')
        
        logo = request.files.get('logo')
        if logo and logo.filename != '':
            filename = secure_filename(logo.filename)
            unique_filename = f"logo_{uuid.uuid4().hex[:8]}_{filename}"
            # Save directly to GridFS to support Vercel serverless environment
            file_id = fs.put(logo, filename=unique_filename, content_type=logo.content_type)
            config_data['logo_url'] = url_for('get_file', file_id=str(file_id))
            config_data['logo_filename'] = filename
            
        config_data['school_name'] = school_name
        config_data['academic_year'] = academic_year
        config_data['MAIL_USERNAME'] = request.form.get('MAIL_USERNAME')
        config_data['MAIL_PASSWORD'] = request.form.get('MAIL_PASSWORD')
        config_data['TWILIO_ACCOUNT_SID'] = request.form.get('TWILIO_ACCOUNT_SID')
        config_data['TWILIO_AUTH_TOKEN'] = request.form.get('TWILIO_AUTH_TOKEN')
        config_data['TWILIO_PHONE_NUMBER'] = request.form.get('TWILIO_PHONE_NUMBER')
        config_data['SENDGRID_API_KEY'] = request.form.get('SENDGRID_API_KEY')
        config_data['SENDGRID_FROM_EMAIL'] = request.form.get('SENDGRID_FROM_EMAIL')
        config_data['GEMINI_API_KEY'] = request.form.get('GEMINI_API_KEY')
        
        if db.settings.count_documents({}) == 0:
            db.settings.insert_one(config_data)
        else:
            db.settings.update_one({}, {'$set': config_data})
            
        flash('Settings saved successfully.')
        return redirect(url_for('settings'))
        
    return render_template('settings.html', config_data=config_data)
@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    if isinstance(e, Exception):
        error_type = type(e).__name__
        error_msg = str(e)
        tb = traceback.format_exc()
        
        url = request.url if request else "Unknown URL"
        method = request.method if request else "Unknown Method"
        user = session.get('email', 'Guest') if session else "Unknown"
        
        full_details = f"User: {user}\nMethod: {method}\nURL: {url}\n\nError: {error_type} - {error_msg}\n\nTraceback:\n{tb}"
        print(f"\n--- [CRITICAL ERROR] ---\n{full_details}\n-----------------------\n")
        
        # Send async so it doesn't block the response
        threading.Thread(target=send_error_email, args=(full_details,)).start()
        
        # Also log to DB notification system
        log_notification("System Error", f"{error_type}: {error_msg}", type="error")
        
        return "<h1>500 Internal Server Error</h1><p>Oops, something went wrong. The system administrator has been notified.</p>", 500
    return e

@app.route('/dev/test_error')
def dev_test_error():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return "Unauthorized", 403
    # Artificially trigger an exception
    raise ValueError("This is a simulated system crash to test automated email notifications!")

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
