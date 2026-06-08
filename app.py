import json
import os
import uuid
import random
import string
import csv
import io
from datetime import datetime, timedelta
import threading
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, make_response, send_file
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


load_dotenv()

# Setup MongoDB
mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(mongo_uri)
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
        print(f"Failed to send email to {email}: {e}")

def configure_gemini():
    config_data = db.settings.find_one({}, {'_id': 0}) or {}
    api_key = config_data.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
    if api_key:
        client = genai.Client(api_key=api_key)
        return client, api_key
    return None, None

configure_gemini()

app = Flask(__name__)
app.secret_key = 'super_secret_key_change_in_production'



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
    refresh_mail_config()
    subject = "Your OTP Code"
    body = f"Your OTP is: {otp}"
    print(f"\n--- [DEV] OTP for {email}: {otp} ---\n")
    try:
        msg = Message(subject, sender=app.config.get('MAIL_USERNAME'), recipients=[email])
        msg.body = body
        mail.send(msg)
        print(f"Sent OTP email to {email}")
        return True
    except Exception as e:
        error_msg = str(e)
        print(f"Error sending email via SMTP: {error_msg}")
        return error_msg

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
        
        if login_type == 'student':
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
        
    return render_template('student_profile.html', student=student)

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
        db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
