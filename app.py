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
from flask_socketio import SocketIO, emit, join_room, leave_room
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
        raise ValueError("Twilio credentials not configured")

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
        raise ValueError("SendGrid credentials not configured")

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
        raise e

def send_error_email(error_details):
    # PERMANENTLY DISABLED - Do not send any error alert emails
    return False

def configure_gemini():
    try:
        config_data = db.settings.find_one({}, {'_id': 0}) or {}
        api_key = config_data.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
        if api_key:
            client = genai.Client(api_key=api_key)
            return client, api_key
    except Exception as e:
        print(f"Warning: Failed to configure Gemini during startup. Error: {e}")
    return None, None

configure_gemini()

app = Flask(__name__)
_secret_key = os.environ.get('SECRET_KEY', '')
if not _secret_key:
    import warnings
    warnings.warn(
        "SECRET_KEY environment variable is not set. "
        "Using an insecure default — set SECRET_KEY in your .env file before deploying.",
        stacklevel=2
    )
    _secret_key = 'super_secret_key_change_in_production'
app.secret_key = _secret_key
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

import re

def get_class_variations(cls_str):
    if not cls_str:
        return []
    cls_str = str(cls_str).strip()
    if cls_str.lower() == 'all':
        return ['all']
        
    variations = {cls_str}
    
    # Extract the first numeric part
    m = re.search(r'\d+', cls_str)
    if m:
        num = m.group()
        variations.add(num)
        variations.add(f"Grade {num}")
        variations.add(f"Class {num}")
        
        # Add suffix version
        if num == '1':
            variations.add('1st')
            variations.add('1st Standard')
        elif num == '2':
            variations.add('2nd')
            variations.add('2nd Standard')
        elif num == '3':
            variations.add('3rd')
            variations.add('3rd Standard')
        else:
            variations.add(f"{num}th")
            variations.add(f"{num}th Standard")
            
    return list(variations)

def get_student_query(base_query=None):
    if base_query is None:
        base_query = {}
    
    if session.get('role') == 'teacher':
        assigned_class = session.get('assigned_class')
        if assigned_class and assigned_class != 'all':
            base_query['student_class'] = {'$in': get_class_variations(assigned_class)}
            
    return base_query

def has_permission(permission_name):
    """Check if the current user has a specific permission based on their role."""
    if not session.get('logged_in'):
        return False
    role = session.get('role', 'student')
    if role == 'admin':
        return True
        
    if role == 'teacher' and permission_name == 'manage_grades':
        return True
        
    try:
        global_config = db.role_permissions.find_one({'_id': 'global_config'})
        if global_config and global_config.get(role):
            return global_config[role].get(permission_name, False)
    except Exception:
        pass
    # Defaults for built-in roles
    if role == 'teacher':
        defaults = {'view_dashboard': True, 'manage_students': True, 'edit_materials': True, 'modify_attendance': True, 'manage_grades': True}
        return defaults.get(permission_name, False)
    return False

@app.context_processor
def inject_global_context():
    context = {'active_announcements': [], 'role_permissions': {}}
    if not session.get('logged_in'):
        return context
    
    role = session.get('role', 'student')
    target = ['all']
    if role in ('admin', 'teacher') or role not in ('student',):
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
                'ai_insights': True,
                'manage_grades': True
            }
        else:
            global_config = db.role_permissions.find_one({'_id': 'global_config'})
            if global_config and global_config.get(role):
                context['role_permissions'] = global_config[role]
            else:
                # Defaults
                if role == 'teacher':
                    context['role_permissions'] = {'view_dashboard': True, 'manage_students': True, 'edit_materials': True, 'modify_attendance': True, 'manage_grades': True}
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
            'ai_insights': False,
            'manage_grades': False
        }
        
        # Upsert the new role into global_config
        db.role_permissions.update_one(
            {'_id': 'global_config'},
            {'$set': {role_name: default_permissions}},
            upsert=True
        )
        
        log_notification(
            "Custom Role Added", 
            f"A new role '{role_name}' has been created by {session.get('username', 'Admin')}.", 
            type='success', 
            role_target='admin'
        )
        
        return jsonify({'success': True, 'role': role_name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roles/<role_name>', methods=['DELETE'])
def delete_custom_role(role_name):
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    try:
        role_name = role_name.strip().lower()
        reserved = ['admin', 'teacher', 'student', '_id']
        if role_name in reserved:
            return jsonify({'success': False, 'error': 'Cannot delete built-in roles'}), 400
        
        # Remove role from global_config
        db.role_permissions.update_one(
            {'_id': 'global_config'},
            {'$unset': {role_name: ''}}
        )
        
        # Reset any users with this custom role back to 'teacher'
        db.users.update_many(
            {'custom_role': role_name},
            {'$unset': {'custom_role': ''}}
        )
        
        log_notification(
            "Custom Role Deleted",
            f"Role '{role_name}' has been removed by {session.get('username', 'Admin')}. Affected users reset to 'teacher'.",
            type='success',
            role_target='admin'
        )
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<user_id>/role', methods=['POST'])
def assign_user_role(user_id):
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    try:
        data = request.json
        new_role = data.get('role', '').strip().lower()
        
        if not new_role:
            return jsonify({'success': False, 'error': 'Role name is required'}), 400
        
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get('email', 'Unknown')
        
        if new_role == 'teacher':
            # Reset to default teacher role
            db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$unset': {'custom_role': ''}}
            )
        else:
            # Verify the custom role exists
            global_config = db.role_permissions.find_one({'_id': 'global_config'})
            if not global_config or not global_config.get(new_role):
                return jsonify({'success': False, 'error': f"Role '{new_role}' does not exist. Create it first."}), 400
            
            db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'custom_role': new_role}}
            )
        
        log_notification(
            "User Role Updated",
            f"{user_name}'s role changed to '{new_role}' by {session.get('username', 'Admin')}.",
            type='success',
            role_target='admin'
        )
        
        return jsonify({'success': True, 'role': new_role, 'user_name': user_name})
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

# /dev/wipe_users has been permanently removed (unauthenticated destructive endpoint).



# ---------------------------------------------------------------------------
# SMTP / Flask-Mail configuration
# All values come from .env (or Vercel environment variables).
# No credentials are hardcoded here — set them in your .env file:
#   MAIL_SERVER=smtp.office365.com
#   MAIL_PORT=587
#   MAIL_USERNAME=agent4@indusschool.com
#   MAIL_PASSWORD=Agent@2026
# ---------------------------------------------------------------------------
def _get_smtp_config():
    """
    Load SMTP settings. MAIL_SERVER is intentionally NOT read from
    environment variables because Vercel / deployment environments often
    carry a stale 'MAIL_SERVER=smtp.gmail.com' value that silently
    redirects all emails to Gmail (causing 535 gsmtp auth failures).

    Credential priority (MAIL_USERNAME / MAIL_PASSWORD only):
      1. Environment variables / .env  <-- PRIMARY
      2. db.settings (admin-configurable via Settings page)

    Server is always smtp.office365.com unless overridden in db.settings.
    """
    # --- Credentials from environment ---
    username = os.environ.get('MAIL_USERNAME', '').strip()
    password = os.environ.get('MAIL_PASSWORD', '').strip()

    # --- All config from db.settings (fills gaps + provides server) ---
    try:
        cfg = db.settings.find_one({}, {'_id': 0}) or {}
    except Exception:
        cfg = {}

    username = username or cfg.get('MAIL_USERNAME', '')
    password = password or cfg.get('MAIL_PASSWORD', '')

    # Server and port come ONLY from db.settings or default — never from env
    server   = cfg.get('MAIL_SERVER', '') or 'smtp.office365.com'
    try:
        port = int(cfg.get('MAIL_PORT', 587))
    except (ValueError, TypeError):
        port = 587

    if not username:
        raise RuntimeError(
            'SMTP username not configured. '
            'Set MAIL_USERNAME in your .env file or in the Settings page.'
        )
    if not password:
        raise RuntimeError(
            'SMTP password not configured. '
            'Set MAIL_PASSWORD in your .env file or in the Settings page.'
        )

    return {'server': server, 'port': port, 'username': username, 'password': password}


def refresh_mail_config():
    """Refresh Flask-Mail config from environment / db.settings."""
    try:
        cfg = _get_smtp_config()
        app.config['MAIL_SERVER']   = cfg['server']
        app.config['MAIL_PORT']     = cfg['port']
        app.config['MAIL_USE_TLS']  = True
        app.config['MAIL_USERNAME'] = cfg['username']
        app.config['MAIL_PASSWORD'] = cfg['password']
    except RuntimeError as e:
        print(f'[MAIL CONFIG] Warning: {e}')
        # Set safe defaults so Flask-Mail doesn't crash at import time
        app.config.setdefault('MAIL_SERVER',   'smtp.office365.com')
        app.config.setdefault('MAIL_PORT',     587)
        app.config.setdefault('MAIL_USE_TLS',  True)
        app.config.setdefault('MAIL_USERNAME', '')
        app.config.setdefault('MAIL_PASSWORD', '')


app.config['MAIL_USE_TLS'] = True   # needed before Mail(app) init
refresh_mail_config()
mail = Mail(app)

# ---------------------------------------------------------------------------
# Flask-SocketIO — Real-Time WebSocket Notifications
# Uses eventlet for async. Falls back to threading if eventlet unavailable.
# ---------------------------------------------------------------------------
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

@socketio.on('connect')
def on_connect():
    """Client connected — join their role-based room for targeted broadcasts."""
    if session.get('logged_in'):
        role = session.get('role', 'student')
        user_id = str(session.get('user_id', ''))
        join_room(role)          # role room: 'admin', 'teacher', 'student'
        join_room(user_id)       # personal room for direct messages
        join_room('all')         # broadcast room for everyone
        emit('connected', {'status': 'ok', 'role': role})

@socketio.on('disconnect')
def on_disconnect():
    pass

def broadcast_notification(title, message, notif_type='info', role_target='all'):
    """
    Save notification to DB and push it in real-time to all connected clients
    in the target room via SocketIO.
    role_target: 'all', 'admin', 'teacher', 'student'
    """
    log_notification(title, message, type=notif_type, role_target=role_target)
    payload = {
        'title': title,
        'message': message,
        'type': notif_type,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    socketio.emit('new_notification', payload, room=role_target)
    if role_target != 'all':
        # Also push to 'all' room watchers (admins see everything)
        socketio.emit('new_notification', payload, room='admin')


def recalculate_students_attendance():
    students = list(db.students.find(get_student_query()))
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
    """Send an OTP or password-reset code via SMTP.

    All credentials and server settings are loaded from:
      1. Environment variables in .env  (MAIL_SERVER, MAIL_PORT,
         MAIL_USERNAME, MAIL_PASSWORD)
      2. db.settings (admin-configurable via the Settings page)
    No credentials are hardcoded in this function.
    """
    try:
        cfg = _get_smtp_config()
    except RuntimeError as e:
        print(f'[OTP] Configuration error: {e}')
        return str(e)

    smtp_server = cfg['server']
    smtp_port   = cfg['port']
    smtp_user   = cfg['username']
    smtp_pass   = cfg['password']

    subject = (
        'Password Reset Code - Indus Portal'
        if is_reset else
        'Your OTP Code - Indus Portal'
    )
    body = (
        f'Your verification code is: {otp}\n\n'
        f'This code expires in 5 minutes.\n\n'
        f'Regards,\nIndus Portal'
    )
    print(f'\n[OTP] Sending to {email} via {smtp_server}:{smtp_port} as {smtp_user}\n')

    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From']    = smtp_user
        msg['To']      = email

        server = smtplib.SMTP(smtp_server, smtp_port, timeout=20)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, email, msg.as_string())
        server.quit()
        print(f'[OTP] ✓ Delivered to {email}')
        return True
    except Exception as e:
        error_msg = str(e)
        print(f'[OTP] ✗ Failed to deliver to {email}: {error_msg}')
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
                    'password': generate_password_hash('Kalmeshwar@123'),
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
            
            if auth_user and (check_password_hash(auth_user.get('password', ''), student_id_or_password) or auth_user.get('password') == student_id_or_password):
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
                session['role'] = user.get('custom_role', 'teacher')
                session['assigned_class'] = user.get('assigned_class', 'all')
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

@app.route('/admin-portal', methods=['GET', 'POST'])
def admin_portal():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form.get('password', '')
        
        if not db.admins.find_one({'email': 'kalmeshwargurav1028@gmail.com'}):
            db.admins.insert_one({
                'email': 'kalmeshwargurav1028@gmail.com',
                'password': generate_password_hash('Kalmeshwar@123'),
                'name': 'System Admin'
            })
            
        admin = db.admins.find_one({'email': email})
        if admin and (admin.get('password') == password or check_password_hash(admin.get('password', ''), password)):
            session['logged_in'] = True
            session['role'] = 'admin'
            session['user_id'] = str(admin['_id'])
            session['username'] = admin.get('name', 'Admin')
            session['email'] = email
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials. Please try again.')
            
    return render_template('admin_portal.html')

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
                'password': generate_password_hash(password)
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
            'password': generate_password_hash(password),
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
                    db.users.update_one({'email': email}, {'$set': {'password': generate_password_hash(new_password)}})
                if student:
                    db.student_users.update_one({'email': email}, {'$set': {'password': generate_password_hash(new_password)}})
                if student_profile:
                    db.students.update_one({'email': email}, {'$set': {'password': generate_password_hash(new_password)}})
                    
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

@app.route('/', methods=['GET', 'POST'])
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('role') == 'student':
        return redirect(url_for('student_profile', student_id=session.get('user_id')))
    
    students = list(db.students.find(get_student_query(), {'_id': 0}))
    
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

@app.route('/student/<student_id>/ai_mentor')
def student_ai_mentor(student_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if session.get('role') == 'student' and session.get('user_id') != student_id:
        flash('You can only access your own AI Mentor.')
        return redirect(url_for('dashboard'))
        
    student = db.students.find_one(get_student_query({'id': student_id}), {'_id': 0})
    if not student:
        flash('Student not found.')
        return redirect(url_for('dashboard'))
        
    return render_template('student_ai_mentor.html', student=student)

@app.route('/student/<student_id>')
def student_profile(student_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    student = db.students.find_one(get_student_query({'id': student_id}), {'_id': 0})
    
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
        
    # Fetch real grades from the gradebook
    real_grades = list(db.grades.find({'student_id': student_id}))
    if real_grades:
        if 'subjects' not in student or not isinstance(student['subjects'], dict):
            student['subjects'] = {}
        for g in real_grades:
            subj = g.get('subject')
            ca = float(g.get('ca_mark') or 0)
            exam = float(g.get('exam_mark') or 0)
            student['subjects'][subj] = ca + exam
        
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
            'last_active': last_active_str or 'Never',
            'custom_role': t.get('custom_role', 'teacher')
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
    student_profiles = {s['id']: s for s in db.students.find(get_student_query(), {'_id': 0})}
    
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
    
    # Build list of available roles for assignment dropdown
    available_roles = ['teacher']
    for key in global_config:
        if key not in ('_id', 'admin', 'teacher', 'student'):
            available_roles.append(key)
    
    return render_template('admin_dashboard.html', stats=stats, active_admins=active_admins, inactive_admins=inactive_admins, active_teachers=active_teachers, inactive_teachers=inactive_teachers, active_students=active_students, inactive_students=inactive_students, materials=materials, announcements=announcements, now_time=now_time, global_config=global_config, available_roles=available_roles)

@app.route('/staff_management')
def staff_management():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    # Get all teachers and admins
    staff_members = list(db.users.find({'role': {'$in': ['teacher', 'admin']}}, {'password': 0}))
    return render_template('staff_management.html', staff_members=staff_members)

@app.route('/api/staff/add', methods=['POST'])
def add_staff():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    role = request.form.get('role', 'teacher')
    assigned_class = request.form.get('assigned_class', 'all')
    password = request.form.get('password', '')
    
    if not all([first_name, last_name, email, password]):
        return jsonify({'success': False, 'error': 'All fields are required'}), 400
        
    try:
        existing_user = db.users.find_one({'email': email})
        if existing_user:
            return jsonify({'success': False, 'error': 'User with this email already exists'}), 400
            
        hashed_password = generate_password_hash(password)
        
        new_staff = {
            'first_name': first_name,
            'last_name': last_name,
            'name': f"{first_name} {last_name}",
            'email': email,
            'role': role,
            'assigned_class': assigned_class,
            'password': hashed_password,
            'created_at': datetime.utcnow().isoformat()
        }
        
        db.users.insert_one(new_staff)
        
        log_notification(
            "Staff Member Created", 
            f"Admin {session.get('username')} created a new {role}: {first_name} {last_name}.", 
            role_target='admin'
        )
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': f"Error: {str(e)}"}), 500

@app.route('/api/staff/delete/<staff_id>', methods=['POST'])
def delete_staff(staff_id):
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    # Prevent self-deletion
    if str(staff_id) == session.get('user_id'):
        return jsonify({'success': False, 'error': 'You cannot delete your own account.'}), 400
        
    try:
        result = db.users.delete_one({'_id': ObjectId(staff_id)})
        if result.deleted_count > 0:
            log_notification(
                "Staff Member Deleted", 
                f"Admin {session.get('username')} deleted staff member with ID {staff_id}.", 
                role_target='admin'
            )
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Staff member not found.'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': f"Database error: {str(e)}"}), 500

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

@app.route('/timetable', methods=['GET', 'POST'])
def timetable():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    role = session.get('role')
    
    if request.method == 'POST':
        if role == 'student':
            return redirect(url_for('timetable'))
            
        action = request.form.get('action')
        if action == 'add':
            db.timetable.insert_one({
                'day': request.form.get('day'),
                'time': request.form.get('time'),
                'subject': request.form.get('subject'),
                'room': request.form.get('room'),
                'teacher': session.get('username') or request.form.get('teacher'),
                'class_name': request.form.get('class_name')
            })
            flash('Timetable entry added!')
        elif action == 'delete':
            db.timetable.delete_one({'_id': ObjectId(request.form.get('id'))})
            flash('Timetable entry deleted!')
        return redirect(url_for('timetable'))
        
    # Get entries
    query = {}
    if role == 'student':
        student = db.students.find_one(get_student_query({'id': session.get('user_id')}))
        if student and student.get('student_class'):
            query['class_name'] = {'$in': get_class_variations(student.get('student_class'))}
        else:
            # No class assigned — return empty timetable rather than all entries
            query['class_name'] = '__no_class__'
    elif role == 'teacher':
        query['teacher'] = session.get('username')
        
    entries = list(db.timetable.find(query))
    
    # Organize by day
    timetable_data = {'Monday': [], 'Tuesday': [], 'Wednesday': [], 'Thursday': [], 'Friday': []}
    for e in entries:
        day = e.get('day')
        if day in timetable_data:
            timetable_data[day].append(e)
            
    # Sort by time string (basic sorting)
    for day in timetable_data:
        timetable_data[day] = sorted(timetable_data[day], key=lambda x: x.get('time', ''))
        
    current_day = datetime.now().strftime('%A')
    
    template_name = 'student_timetable.html' if role == 'student' else 'teacher_timetable.html'
    return render_template(template_name, timetable=timetable_data, current_day=current_day)

@app.route('/assignments', methods=['GET', 'POST'])
def assignments():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    role = session.get('role')
    now = datetime.now()
    
    if request.method == 'POST':
        if role == 'student':
            # Handle submission
            assignment_id = request.form.get('assignment_id')
            db.assignments.update_one(
                {'_id': ObjectId(assignment_id)},
                {'$push': {'submissions': {
                    'student_id': session.get('user_id'),
                    'student_name': session.get('username'),
                    'submitted_at': now.strftime('%Y-%m-%d %H:%M'),
                    'grade': None
                }}}
            )
            flash('Assignment submitted!')
        else:
            action = request.form.get('action')
            if action == 'create':
                file = request.files.get('assignment_file')
                file_id = None
                filename = None
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    file_id = str(fs.put(file, filename=filename, content_type=file.content_type))
                    
                db.assignments.insert_one({
                    'title': request.form.get('title'),
                    'subject': request.form.get('subject'),
                    'class_name': request.form.get('class_name'),
                    'gradebook_category': request.form.get('gradebook_category'),
                    'max_points': request.form.get('max_points'),
                    'due_date': request.form.get('due_date'),
                    'description': request.form.get('description'),
                    'file_id': file_id,
                    'filename': filename,
                    'created_by': session.get('username'),
                    'submissions': []
                })
                flash('Assignment created!')
            elif action == 'grade':
                assignment_id = request.form.get('assignment_id')
                student_id = request.form.get('student_id')
                grade = request.form.get('grade')
                
                db.assignments.update_one(
                    {'_id': ObjectId(assignment_id), 'submissions.student_id': student_id},
                    {'$set': {'submissions.$.grade': grade}}
                )
                flash('Grade saved!')
            elif action == 'delete':
                db.assignments.delete_one({'_id': ObjectId(request.form.get('id'))})
                flash('Assignment deleted!')
                
        return redirect(url_for('assignments'))
        
    # Get entries
    query = {}
    if role == 'student':
        student = db.students.find_one(get_student_query({'id': session.get('user_id')}))
        if student and student.get('student_class'):
            query['class_name'] = {'$in': get_class_variations(student.get('student_class'))}
        else:
            query['class_name'] = '__no_class__'
    elif role == 'teacher':
        query['created_by'] = session.get('username')
        
    assignments_data = list(db.assignments.find(query).sort('due_date', 1))
    
    # Enrich data for students
    if role == 'student':
        for a in assignments_data:
            due_date_str = a.get('due_date')
            try:
                due = datetime.strptime(due_date_str, '%Y-%m-%d')
                days_left = (due - now).days
                a['days_left'] = days_left
            except:
                a['days_left'] = 0
                
            subs = a.get('submissions', [])
            my_sub = next((s for s in subs if s['student_id'] == session.get('user_id')), None)
            if my_sub:
                a['status'] = 'submitted'
                a['my_grade'] = my_sub.get('grade')
            else:
                a['status'] = 'pending' if a['days_left'] >= 0 else 'overdue'
                
    return render_template('assignments.html', assignments=assignments_data)

@app.route('/daily_logs', methods=['GET', 'POST'])
def daily_logs():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    role = session.get('role')
    
    if request.method == 'POST':
        if role != 'student':
            db.daily_logs.insert_one({
                'date': request.form.get('date'),
                'class_name': request.form.get('class_name'),
                'subject': request.form.get('subject'),
                'topics': request.form.get('topics'),
                'remarks': request.form.get('remarks'),
                'teacher': session.get('username')
            })
            flash('Daily log added successfully!')
        return redirect(url_for('daily_logs'))
        
    # Get entries
    query = {}
    if role == 'student':
        student = db.students.find_one(get_student_query({'id': session.get('user_id')}))
        if student and student.get('student_class'):
            query['class_name'] = student.get('student_class')
        else:
            query['class_name'] = '__no_class__'
            
    logs = list(db.daily_logs.find(query).sort('date', -1).limit(50))
    
    template_name = 'student_daily_logs.html' if role == 'student' else 'teacher_daily_logs.html'
    return render_template(template_name, logs=logs, current_date=datetime.now().strftime('%Y-%m-%d'))


@app.route('/parent_portal', methods=['GET', 'POST'])
def parent_portal():
    if not session.get('logged_in') or session.get('role') != 'student':
        flash('Parent Portal is only accessible through a student account.')
        return redirect(url_for('login'))
        
    student_id = session.get('user_id')
    student = db.students.find_one(get_student_query({'id': student_id}), {'_id': 0})
    if not student:
        # Fallback to student_users table if student profile doesn't exist
        student = db.student_users.find_one({'student_id': student_id}, {'_id': 0})
        if not student:
            return redirect(url_for('login'))
            
    if request.method == 'POST':
        subject = request.form.get('subject')
        message = request.form.get('message')
        if subject and message:
            db.messages.insert_one({
                'student_id': student_id,
                'student_name': student.get('name', session.get('username')),
                'subject': subject,
                'message': message,
                'date_sent': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'status': 'unread'
            })
            flash('Your message has been sent to the teacher successfully!')
        return redirect(url_for('parent_portal'))
        
    # Fetch recent assignments (last 5)
    query = {}
    if student.get('student_class'):
        query['class_name'] = {'$in': get_class_variations(student.get('student_class'))}
    
    assignments_data = list(db.assignments.find(query).sort('due_date', -1).limit(5))
    
    # Process submissions to find the student's grade
    for a in assignments_data:
        subs = a.get('submissions', [])
        my_sub = next((s for s in subs if s['student_id'] == student_id), None)
        if my_sub and my_sub.get('grade'):
            a['my_grade'] = my_sub.get('grade')
            
    # Fetch recent daily logs/discipline (last 5)
    daily_logs = list(db.daily_logs.find(query).sort('date', -1).limit(5))
    
    return render_template('parent_portal.html', student=student, recent_assignments=assignments_data, daily_logs=daily_logs)


@app.route('/student/materials')
def student_materials():
    if not session.get('logged_in') or session.get('role') != 'student':
        return redirect(url_for('login'))
        
    student_id = session.get('user_id')
    student = db.students.find_one(get_student_query({'id': student_id}), {'_id': 0})
    if not student:
        return redirect(url_for('login'))
        
    student_class = student.get('student_class')
    materials = []
    if student_class:
        materials = list(db.materials.find({'class': {'$in': get_class_variations(student_class)}}).sort('uploaded_at', -1))
        
    return render_template('student_materials.html', student=student, materials=materials)

@app.route('/student/<student_id>/id_card')
def student_id_card(student_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    student = db.students.find_one(get_student_query({'id': student_id}), {'_id': 0})
    
    if not student:
        flash('Student not found.')
        return redirect(url_for('dashboard'))
        
    return render_template('id_card.html', student=student)

@app.route('/student/<student_id>/academic_profile_pdf')
def academic_profile_pdf(student_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    student = db.students.find_one(get_student_query({'id': student_id}), {'_id': 0})
    if not student:
        flash('Student not found.')
        return redirect(url_for('dashboard'))
        
    # Calculate cumulative total marks
    total_marks = 0
    max_marks = 0
    subjects_breakdown = {}
    
    if student.get('subjects'):
        for subj, score in student.get('subjects').items():
            total_marks += float(score)
            max_marks += 100
            subjects_breakdown[subj] = f"{score}/100"
            
    # Also look at grades collection if any
    grades = list(db.grades.find({'student_id': student_id}, {'_id': 0}))
    for g in grades:
        subj = g.get('subject')
        ca = float(g.get('ca_mark') or 0)
        exam = float(g.get('exam_mark') or 0)
        if subj not in subjects_breakdown:
            total = ca + exam
            total_marks += total
            max_marks += 100
            subjects_breakdown[subj] = f"{ca} + {exam} = {total}/100"

    return render_template('academic_profile_pdf.html', 
                          student=student, 
                          total_marks=total_marks, 
                          max_marks=max_marks, 
                          subjects_breakdown=subjects_breakdown)

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
    student = db.students.find_one(get_student_query({'id': student_id}), {'_id': 0}) if student_id else None

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
        
    student = db.students.find_one(get_student_query({'id': student_id}), {'_id': 0})
    
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
        
    students = list(db.students.find(get_student_query(), {'_id': 0}))
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
    if not has_permission('modify_attendance'):
        flash('You do not have permission to access Attendance.')
        return redirect(url_for('dashboard'))
        
    selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d')) or datetime.now().strftime('%Y-%m-%d')
    mode = request.args.get('mode', 'homeroom')
    target_class = request.args.get('target_class', '')
    subject = request.args.get('subject', '')
    
    if mode == 'universal' and target_class:
        students = list(db.students.find({'student_class': {'$in': get_class_variations(target_class)}}, {'_id': 0}))
    else:
        students = list(db.students.find(get_student_query(), {'_id': 0}))
    
    if request.method == 'POST':
        mode_post = request.form.get('mode', 'homeroom')
        target_class_post = request.form.get('target_class', '')
        
        if mode_post == 'universal' and target_class_post:
            post_students = list(db.students.find({'student_class': {'$in': get_class_variations(target_class_post)}}, {'_id': 0}))
        else:
            post_students = list(db.students.find(get_student_query(), {'_id': 0}))
            
        update_fields = {}
        for s in post_students:
            s_id = s['id']
            status = request.form.get(f'status_{s_id}')
            if status in ['Present', 'Absent', 'Late']:
                update_fields[f'records.{s_id}'] = status
            else:
                update_fields[f'records.{s_id}'] = 'Present'
                
        if update_fields:
            db.attendance.update_one(
                {'date': selected_date},
                {'$set': update_fields},
                upsert=True
            )
        
        # Trigger recalculation
        recalculate_students_attendance()
        
        # --- Absent alerts: send SMS/email to parent for EVERY absent student ---
        alerts_sent = 0
        for s in post_students:
            s_id = s['id']
            status_today = request.form.get(f'status_{s_id}', 'Present')
            if status_today != 'Absent':
                continue

            att_percentage = float(s.get('attendance', 100))
            name = s.get('name', 'Student')
            school_name = (db.settings.find_one({}, {'school_name': 1}) or {}).get('school_name', 'School')

            # Compose message
            if att_percentage < 75:
                msg = (
                    f"Dear Parent, {name} was ABSENT today ({selected_date}). "
                    f"Current attendance: {att_percentage}% (below the 75% minimum). "
                    f"Please ensure regular attendance. — {school_name}"
                )
                subject = f"Absence Alert — {name} | {school_name}"
            else:
                msg = (
                    f"Dear Parent, {name} was marked ABSENT today ({selected_date}). "
                    f"Current attendance: {att_percentage}%. "
                    f"Please inform the school if this is unexpected. — {school_name}"
                )
                subject = f"Absence Notice — {name} | {school_name}"

            phone = s.get('parent_phone') or s.get('phone')
            email_addr = s.get('parent_email') or s.get('email')

            sent = False
            if phone:
                try:
                    send_twilio_sms(phone, msg)
                    sent = True
                except Exception:
                    pass
            if not sent and email_addr:
                try:
                    send_sendgrid_email(email_addr, subject, msg)
                    sent = True
                except Exception:
                    try:
                        refresh_mail_config()
                        flask_msg = Message(subject,
                                            sender=app.config.get('MAIL_USERNAME'),
                                            recipients=[email_addr])
                        flask_msg.body = msg
                        mail.send(flask_msg)
                        sent = True
                    except Exception as e:
                        print(f"SMTP fallback failed in attendance: {e}")
            if sent:
                alerts_sent += 1
                # Log to parent_alerts collection for the Message Parents page
                db.parent_alerts.insert_one({
                    'student_id': s.get('id'),
                    'student_name': name,
                    'parent_phone': phone,
                    'parent_email': email_addr,
                    'message': msg,
                    'date': selected_date,
                    'sent_by': session.get('username', 'System'),
                    'status': 'sent',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

        if alerts_sent:
            flash(f'Attendance saved. {alerts_sent} parent alert(s) sent for absent students.')
        else:
            flash(f'Attendance for {selected_date} saved successfully.')
        return redirect(url_for('attendance', date=selected_date, mode=mode_post, target_class=target_class_post, subject=request.form.get('subject', '')))
        
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
        stats=stats,
        mode=mode,
        target_class=target_class,
        subject=subject
    )

@app.route('/gradebook', methods=['GET', 'POST'])
def gradebook():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('role') == 'student':
        return redirect(url_for('student_gradebook', student_id=session.get('user_id')))
    if not has_permission('manage_grades'):
        flash('You do not have permission to access Gradebook.')
        return redirect(url_for('dashboard'))

    students = list(db.students.find(get_student_query(), {'_id': 0}))
    subjects = ['Mathematics', 'Physics', 'Chemistry', 'Biology', 'English', 'History']

    if request.method == 'POST':
        for s in students:
            s_id = s['id']
            for sub in subjects:
                ca = request.form.get(f'ca_{s_id}_{sub}', '')
                exam = request.form.get(f'exam_{s_id}_{sub}', '')
                if ca or exam:
                    db.grades.update_one(
                        {'student_id': s_id, 'subject': sub},
                        {'$set': {'ca_mark': ca, 'exam_mark': exam}},
                        upsert=True
                    )
        flash('Grades updated successfully!')
        return redirect(url_for('gradebook'))

    # Prepare grades dict for the template
    all_grades = list(db.grades.find({}, {'_id': 0}))
    grades_dict = {}
    for g in all_grades:
        sid = g.get('student_id')
        sub = g.get('subject')
        if sid not in grades_dict:
            grades_dict[sid] = {}
        grades_dict[sid][sub] = g

    return render_template(
        'gradebook.html',
        students=students,
        subjects=subjects,
        grades_dict=grades_dict
    )

@app.route('/student/<student_id>/gradebook')
def student_gradebook(student_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    if session.get('role') == 'student' and session.get('user_id') != student_id:
        flash('You can only view your own gradebook.')
        return redirect(url_for('dashboard'))
        
    student = db.students.find_one(get_student_query({'id': student_id}), {'_id': 0})
    if not student:
        flash('Student not found.')
        return redirect(url_for('dashboard'))

    student_grades = list(db.grades.find({'student_id': student_id}, {'_id': 0}))
    
    # Calculate totals and format for display
    grades_display = []
    for g in student_grades:
        ca = float(g.get('ca_mark') or 0)
        exam = float(g.get('exam_mark') or 0)
        total = ca + exam
        g['total'] = total
        grades_display.append(g)

    return render_template('student_gradebook.html', student=student, grades=grades_display)

@app.route('/materials', methods=['GET', 'POST'])
def materials():
    if not session.get('logged_in') or session.get('role') == 'student':
        return redirect(url_for('login'))
    if not has_permission('edit_materials'):
        flash('You do not have permission to access Study Materials.')
        return redirect(url_for('dashboard'))
        
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

@app.route('/material/edit/<material_id>', methods=['POST'])
def edit_material(material_id):
    if not session.get('logged_in') or session.get('role') == 'student':
        return redirect(url_for('login'))
    
    title = request.form.get('title')
    student_class = request.form.get('student_class')
    subject = request.form.get('subject')
    file = request.files.get('file')
    
    update_data = {
        'title': title,
        'class': student_class,
        'subject': subject
    }
    
    # If a new file is uploaded, replace the old one
    if file and file.filename != '':
        # Delete old file from GridFS
        material = db.materials.find_one({'_id': ObjectId(material_id)})
        if material and material.get('file_url'):
            try:
                old_file_id = material['file_url'].split('/file/')[-1]
                fs.delete(ObjectId(old_file_id))
            except Exception:
                pass
        
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
        file_id = fs.put(file, filename=unique_filename, content_type=file.content_type)
        update_data['file_url'] = url_for('get_file', file_id=str(file_id))
    
    db.materials.update_one(
        {'_id': ObjectId(material_id)},
        {'$set': update_data}
    )
    
    flash('Material updated successfully!')
    return redirect(url_for('materials'))

@app.route('/material/delete/<material_id>', methods=['POST'])
def delete_material(material_id):
    if not session.get('logged_in') or session.get('role') == 'student':
        return redirect(url_for('login'))
    
    material = db.materials.find_one({'_id': ObjectId(material_id)})
    if material:
        # Delete file from GridFS
        if material.get('file_url'):
            try:
                file_id = material['file_url'].split('/file/')[-1]
                fs.delete(ObjectId(file_id))
            except Exception:
                pass
        
        db.materials.delete_one({'_id': ObjectId(material_id)})
        flash('Material deleted successfully!')
    else:
        flash('Material not found.')
    
    return redirect(url_for('materials'))

@app.route('/reports')
def reports():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('role') == 'student':
        return redirect(url_for('student_profile', student_id=session.get('user_id')))
        
    students = list(db.students.find(get_student_query(), {'_id': 0}))
    
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

@app.route('/teacher/daily_report', methods=['GET', 'POST'])
def teacher_daily_report():
    if not session.get('logged_in') or session.get('role') != 'teacher':
        flash('Unauthorized access.')
        return redirect(url_for('login'))
        
    today_date = datetime.now().strftime('%Y-%m-%d')
    today_formatted = datetime.now().strftime('%m / %d / %Y')
    
    if request.method == 'POST':
        classes = request.form.getlist('class[]')
        subjects = request.form.getlist('subject[]')
        topics = request.form.getlist('topics[]')
        remarks = request.form.getlist('remarks[]')
        
        progress_logs = []
        for c, s, t, r in zip(classes, subjects, topics, remarks):
            if c or s or t or r:
                progress_logs.append({
                    'class': c,
                    'subject': s,
                    'topics': t,
                    'remarks': r
                })
                
        db.teacher_reports.insert_one({
            'teacher': session.get('name'),
            'username': session.get('username'),
            'date': today_date,
            'progress_logs': progress_logs,
            'submitted_at': datetime.now()
        })
        flash('Daily report submitted successfully to HOD/Principal.')
        return redirect(url_for('teacher_daily_report'))
        
    # GET method - Calculate attendance snapshot
    att_doc = db.attendance.find_one({'date': today_date})
    records = att_doc.get('records', {}) if att_doc else {}
    
    students = list(db.students.find({}, {'id': 1, 'student_class': 1}))
    class_stats = {}
    for s in students:
        c_name = s.get('student_class')
        if not c_name: continue
        
        if c_name not in class_stats:
            class_stats[c_name] = {'total': 0, 'present': 0}
            
        class_stats[c_name]['total'] += 1
        
        status = records.get(s['id'])
        if status in ['Present', 'Late']:
            class_stats[c_name]['present'] += 1
                
    attendance_snapshot = []
    for c_name, stats in class_stats.items():
        attendance_snapshot.append({
            'class_name': c_name,
            'total': stats['total'],
            'present': stats['present'],
            'absent': stats['total'] - stats['present']
        })
    # Basic sort to put grades in order
    attendance_snapshot.sort(key=lambda x: x['class_name'])
    
    return render_template('teacher_daily_report.html', today_formatted=today_formatted, attendance_snapshot=attendance_snapshot)


@app.route('/ai_box')
def ai_box():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if not has_permission('ai_insights'):
        flash('You do not have permission to access AI Insights.')
        return redirect(url_for('dashboard'))
    return render_template('ai_box.html')

@app.route('/export_students')
def export_students():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    student_class = request.args.get('class', '')
    
    query = {}
    if student_class:
        query['student_class'] = student_class
        
    students = list(db.students.find(get_student_query(query), {'_id': 0}))
        
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


# ===========================================================================
# GLOBAL CLASS ID MAPPING — db.classes registry
# Provides a canonical class document that timetable, assignments, logs,
# and materials can reference by class_id. Resolves the implicit string
# matching problem shown in the architecture diagram.
# ===========================================================================

@app.route('/api/classes', methods=['GET'])
def get_classes():
    """Return all registered class definitions."""
    if not session.get('logged_in'):
        return jsonify([]), 401
    classes = list(db.classes.find({}, {'_id': 0}))
    return jsonify(classes)

@app.route('/api/classes', methods=['POST'])
def create_class():
    """Admin creates a class entry in the global registry."""
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    data = request.json or {}
    class_id = data.get('class_id', '').strip()
    display_name = data.get('display_name', '').strip()
    grade = data.get('grade', '').strip()
    division = data.get('division', 'A').strip()
    homeroom_teacher = data.get('homeroom_teacher', '')

    if not class_id or not display_name:
        return jsonify({'success': False, 'error': 'class_id and display_name are required'}), 400

    existing = db.classes.find_one({'class_id': class_id})
    if existing:
        return jsonify({'success': False, 'error': f"Class '{class_id}' already exists"}), 409

    db.classes.insert_one({
        'class_id': class_id,
        'display_name': display_name,
        'grade': grade,
        'division': division,
        'homeroom_teacher': homeroom_teacher,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    log_notification(
        'Class Registry Updated',
        f"New class '{display_name}' (ID: {class_id}) added by {session.get('username', 'Admin')}.",
        type='success', role_target='admin'
    )
    return jsonify({'success': True, 'class_id': class_id})

@app.route('/api/classes/<class_id_param>', methods=['PUT'])
def update_class(class_id_param):
    """Update homeroom teacher or display name for a class."""
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    data = request.json or {}
    update_fields = {}
    for field in ('display_name', 'homeroom_teacher', 'grade', 'division'):
        if field in data:
            update_fields[field] = data[field]
    if not update_fields:
        return jsonify({'success': False, 'error': 'Nothing to update'}), 400
    db.classes.update_one({'class_id': class_id_param}, {'$set': update_fields})
    return jsonify({'success': True})

@app.route('/api/classes/<class_id_param>', methods=['DELETE'])
def delete_class(class_id_param):
    """Remove a class from the global registry."""
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    db.classes.delete_one({'class_id': class_id_param})
    return jsonify({'success': True})


# ===========================================================================
# TIMETABLE PUBLISH — broadcasts real-time update to all students in the class
# ===========================================================================

@app.route('/api/timetable/publish', methods=['POST'])
def publish_timetable():
    """Teacher publishes their timetable, saves a snapshot, and broadcasts via SocketIO."""
    if not session.get('logged_in') or session.get('role') not in ('teacher', 'admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.json or {}
    class_name = data.get('class_name', '').strip()
    if not class_name:
        return jsonify({'success': False, 'error': 'class_name is required'}), 400

    teacher_name = session.get('username', 'Teacher')
    entries = list(db.timetable.find({'class_name': class_name}, {'_id': 0}))

    db.timetable_published.update_one(
        {'class_name': class_name},
        {'$set': {
            'class_name': class_name,
            'teacher': teacher_name,
            'entries': entries,
            'published_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }},
        upsert=True
    )

    broadcast_notification(
        f'Timetable Updated - {class_name}',
        f'{teacher_name} just published the timetable for {class_name}. Check your schedule.',
        notif_type='info',
        role_target='student'
    )

    log_notification(
        f'Timetable Published: {class_name}',
        f'{teacher_name} published timetable for {class_name}.',
        type='success', role_target='admin'
    )

    socketio.emit('timetable_updated', {
        'class_name': class_name,
        'teacher': teacher_name,
        'entries': entries,
        'published_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }, room='student')

    return jsonify({'success': True, 'entries_count': len(entries)})


# ===========================================================================
# DAILY LOGS SYNC — push real-time event to admin room after saving a log
# ===========================================================================

@app.route('/api/daily_logs/sync', methods=['POST'])
def sync_daily_log():
    """Called after a teacher saves a daily log. Emits SocketIO event to admin room."""
    if not session.get('logged_in') or session.get('role') not in ('teacher', 'admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.json or {}
    class_name = data.get('class_name', '')
    subject = data.get('subject', '')
    date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    teacher = session.get('username', 'Teacher')

    broadcast_notification(
        f'Log Synced - {class_name}',
        f'{teacher} logged {subject} for {class_name} on {date}.',
        notif_type='success',
        role_target='admin'
    )

    socketio.emit('log_synced', {
        'class_name': class_name,
        'subject': subject,
        'date': date,
        'teacher': teacher
    }, room='admin')

    return jsonify({'success': True})


# ===========================================================================
# ASSIGNMENT FILE UPLOAD — teacher uploads PDF/document for an assignment
# ===========================================================================

@app.route('/api/assignments/<assignment_id>/upload', methods=['POST'])
def upload_assignment_file(assignment_id):
    """Upload a PDF/document attachment to an assignment via GridFS."""
    if not session.get('logged_in') or session.get('role') not in ('teacher', 'admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    allowed_extensions = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.txt', '.png', '.jpg', '.jpeg'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return jsonify({'success': False, 'error': f'File type {ext} not allowed'}), 400

    try:
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
        file_id = fs.put(file, filename=unique_filename, content_type=file.content_type)
        file_url = url_for('get_file', file_id=str(file_id))

        db.assignments.update_one(
            {'_id': ObjectId(assignment_id)},
            {'$set': {'file_url': file_url, 'file_name': filename}}
        )

        assignment = db.assignments.find_one({'_id': ObjectId(assignment_id)})
        if assignment:
            class_name = assignment.get('class_name', '')
            title = assignment.get('title', 'Assignment')
            broadcast_notification(
                f'File Attached - {title}',
                f'A document has been attached to "{title}" for {class_name}. Download it from Assignments.',
                notif_type='info',
                role_target='student'
            )

        return jsonify({'success': True, 'file_url': file_url, 'file_name': filename})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===========================================================================
# ADMIN ANALYTICS — Syllabus Pace, Roster Conflicts, Faculty Analytics
# ===========================================================================

@app.route('/api/admin/syllabus_pace', methods=['GET'])
def admin_syllabus_pace():
    """Monitors curriculum compliance by analysing daily log frequency per class (last 30 days)."""
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    logs = list(db.daily_logs.find({'date': {'$gte': thirty_days_ago}}, {'_id': 0}))

    class_counts = {}
    subject_counts = {}
    teacher_counts = {}
    for log in logs:
        cn = log.get('class_name', 'Unknown')
        sub = log.get('subject', 'Unknown')
        teacher = log.get('teacher', 'Unknown')
        class_counts[cn] = class_counts.get(cn, 0) + 1
        subject_counts[sub] = subject_counts.get(sub, 0) + 1
        teacher_counts[teacher] = teacher_counts.get(teacher, 0) + 1

    pace_health = {}
    for cls, count in class_counts.items():
        if count < 10:
            pace_health[cls] = {'count': count, 'status': 'behind', 'color': 'red'}
        elif count < 20:
            pace_health[cls] = {'count': count, 'status': 'on_track', 'color': 'yellow'}
        else:
            pace_health[cls] = {'count': count, 'status': 'ahead', 'color': 'green'}

    return jsonify({
        'pace_health': pace_health,
        'subject_distribution': subject_counts,
        'teacher_log_counts': teacher_counts,
        'period_days': 30,
        'total_logs': len(logs)
    })


@app.route('/api/admin/roster_conflicts', methods=['GET'])
def admin_roster_conflicts():
    """Detects teacher double-booking and room conflicts in the timetable."""
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    entries = list(db.timetable.find({}, {'_id': 0}))
    conflicts = []

    slot_map = {}
    for entry in entries:
        key = (entry.get('day', ''), entry.get('time', ''))
        if key not in slot_map:
            slot_map[key] = []
        slot_map[key].append(entry)

    for (day, time_slot), slot_entries in slot_map.items():
        if len(slot_entries) < 2:
            continue

        teacher_classes = {}
        for e in slot_entries:
            t = e.get('teacher', '')
            if t:
                if t not in teacher_classes:
                    teacher_classes[t] = []
                teacher_classes[t].append(e.get('class_name', ''))
        for teacher, classes in teacher_classes.items():
            if len(classes) > 1:
                conflicts.append({
                    'type': 'teacher_double_booked',
                    'day': day,
                    'time': time_slot,
                    'teacher': teacher,
                    'classes': classes,
                    'severity': 'high',
                    'message': f"{teacher} is scheduled in {', '.join(classes)} simultaneously on {day} at {time_slot}"
                })

        room_classes = {}
        for e in slot_entries:
            room = e.get('room', '')
            if room:
                if room not in room_classes:
                    room_classes[room] = []
                room_classes[room].append({'class': e.get('class_name', ''), 'teacher': e.get('teacher', '')})
        for room, bookings in room_classes.items():
            if len(bookings) > 1:
                conflicts.append({
                    'type': 'room_double_booked',
                    'day': day,
                    'time': time_slot,
                    'room': room,
                    'bookings': bookings,
                    'severity': 'medium',
                    'message': f"Room {room} is double-booked on {day} at {time_slot}"
                })

    return jsonify({
        'conflicts': conflicts,
        'total_conflicts': len(conflicts),
        'has_critical': any(c['severity'] == 'high' for c in conflicts)
    })


@app.route('/api/admin/faculty_analytics', methods=['GET'])
def admin_faculty_analytics():
    """Faculty performance health: log frequency, student outcomes, last active."""
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    teachers = list(db.users.find({}, {'password': 0}))
    students = list(db.students.find(get_student_query(), {'_id': 0}))
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    logs = list(db.daily_logs.find({'date': {'$gte': thirty_days_ago}}, {'_id': 0}))

    log_counts = {}
    for log in logs:
        t = log.get('teacher', '')
        log_counts[t] = log_counts.get(t, 0) + 1

    timetable_entries = list(db.timetable.find({}, {'_id': 0}))
    teacher_classes = {}
    for entry in timetable_entries:
        t = entry.get('teacher', '')
        cn = entry.get('class_name', '')
        if t and cn:
            if t not in teacher_classes:
                teacher_classes[t] = set()
            teacher_classes[t].add(cn)

    class_performance = {}
    for s in students:
        cn = s.get('student_class', '')
        try:
            perf = float(s.get('performance', 0))
        except (ValueError, TypeError):
            perf = 0.0
        if cn not in class_performance:
            class_performance[cn] = []
        class_performance[cn].append(perf)

    avg_class_perf = {cn: round(sum(v)/len(v), 1) for cn, v in class_performance.items() if v}

    result = []
    for t in teachers:
        name = f"{t.get('first_name', '')} {t.get('last_name', '')}".strip() or t.get('email', 'Unknown').split('@')[0]
        classes = list(teacher_classes.get(name, []))
        class_perfs = [avg_class_perf.get(cn, 0) for cn in classes]
        avg_perf = round(sum(class_perfs) / len(class_perfs), 1) if class_perfs else 0
        logs_30d = log_counts.get(name, 0)

        log_score = min(logs_30d / 20, 1.0) * 40
        perf_score = (avg_perf / 100) * 60
        health_score = round(log_score + perf_score, 1)

        result.append({
            'name': name,
            'email': t.get('email', ''),
            'last_active': t.get('last_active', 'Never'),
            'classes_taught': classes,
            'logs_last_30d': logs_30d,
            'avg_student_performance': avg_perf,
            'health_score': health_score,
            'health_label': (
                'excellent' if health_score >= 80 else
                'good' if health_score >= 60 else
                'needs_attention' if health_score >= 40 else
                'at_risk'
            )
        })

    result.sort(key=lambda x: x['health_score'], reverse=True)

    return jsonify({
        'faculty': result,
        'total_teachers': len(result),
        'avg_health_score': round(sum(r['health_score'] for r in result) / len(result), 1) if result else 0
    })



@app.route('/parent_alerts')
def parent_alerts_page():
    """
    Teacher/Admin view: lists all parent alert messages sent, allows
    composing a custom message to any student's parent.
    """
    if not session.get('logged_in') or session.get('role') == 'student':
        return redirect(url_for('login'))

    students = list(db.students.find(get_student_query(), {'_id': 0, 'id': 1, 'name': 1, 'student_class': 1, 'parent_name': 1, 'parent_phone': 1, 'parent_email': 1, 'attendance': 1}))
    # Recent alert log (last 100)
    alerts = list(db.parent_alerts.find().sort('timestamp', -1).limit(100))
    for a in alerts:
        a['_id'] = str(a['_id'])

    return render_template('parent_alerts.html', students=students, alerts=alerts)


@app.route('/api/attendance/send_alert', methods=['POST'])
def send_attendance_alert():
    """
    Manually send a parent alert for a specific student.
    POST JSON: { student_id, message (optional), alert_type: 'absent'|'custom' }
    """
    if not session.get('logged_in') or session.get('role') == 'student':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.json or {}
    student_id = data.get('student_id', '').strip()
    alert_type = data.get('alert_type', 'absent')
    custom_message = data.get('message', '').strip()

    override_name = data.get('override_parent_name', '').strip()
    override_phone = data.get('override_parent_phone', '').strip()
    override_email = data.get('override_parent_email', '').strip()

    if not student_id:
        return jsonify({'success': False, 'error': 'student_id is required'}), 400

    student = db.students.find_one(get_student_query({'id': student_id}), {'_id': 0})
    if not student:
        return jsonify({'success': False, 'error': 'Student not found'}), 404

    name = student.get('name', 'Student')
    att = float(student.get('attendance', 100))
    school_name = (db.settings.find_one({}, {'school_name': 1}) or {}).get('school_name', 'School')
    today = datetime.now().strftime('%Y-%m-%d')

    if custom_message:
        msg = custom_message
        subject = f"Message from {school_name} regarding {name}"
    elif alert_type == 'present':
        msg = (
            f"Dear Parent, {name} is marked PRESENT today ({today}). "
            f"Current attendance: {att}%. "
            f"— {school_name}"
        )
        subject = f"Attendance Notice — {name}"
    elif alert_type == 'absent':
        msg = (
            f"Dear Parent, {name} was marked ABSENT today ({today}). "
            f"Current attendance: {att}%. "
            f"Please contact the school if you have any concerns. — {school_name}"
        )
        subject = f"Absence Notice — {name}"
    elif alert_type == 'homework':
        msg = (
            f"Dear Parent, please remind {name} to complete their pending homework/assignment. "
            f"Regular completion of assignments is important for academic progress. — {school_name}"
        )
        subject = f"Homework Reminder — {name}"
    elif alert_type == 'performance':
        assignments = list(db.assignments.find({'submissions.student_id': student_id}))
        graded = []
        missing = db.assignments.count_documents({'submissions.student_id': {'$ne': student_id}, 'class_name': student.get('student_class')})
        for a in assignments:
            sub = next((s for s in a.get('submissions', []) if s['student_id'] == student_id), None)
            if sub and sub.get('grade'):
                graded.append(f"{a['subject']}: {sub['grade']}")
                
        grades_str = ", ".join(graded[:3]) if graded else "N/A"
        if len(graded) > 3:
            grades_str += "..."
            
        msg = (
            f"Performance Update for {name}:\n"
            f"Attendance: {att}%\n"
            f"Recent Marks: {grades_str}\n"
            f"Missing Assignments: {missing}\n"
            f"— {school_name}"
        )
        subject = f"Performance Update — {name}"
    else:
        msg = f"Dear Parent, this is an update regarding {name} from {school_name}."
        subject = f"School Notice — {name}"

    phone = override_phone if override_phone else (student.get('parent_phone') or student.get('phone'))
    email_addr = override_email if override_email else (student.get('parent_email') or student.get('email'))

    sent_via = []
    if phone:
        try:
            send_twilio_sms(phone, msg)
            sent_via.append('SMS')
        except Exception as e:
            print(f"SMS failed: {e}")
    if email_addr:
        try:
            send_sendgrid_email(email_addr, subject, msg)
            sent_via.append('Email')
        except Exception as e:
            print(f"Email failed: {e}")

    # Also try SMTP as fallback if no SendGrid key
    if 'Email' not in sent_via and email_addr:
        try:
            refresh_mail_config()
            flask_msg = Message(subject,
                                sender=app.config.get('MAIL_USERNAME'),
                                recipients=[email_addr])
            flask_msg.body = msg
            mail.send(flask_msg)
            sent_via.append('Email (SMTP)')
        except Exception as e:
            print(f"SMTP fallback failed: {e}")

    if not sent_via:
        return jsonify({'success': False, 'error': 'No phone or email on record for this student\'s parent.'}), 400

    # Log it
    db.parent_alerts.insert_one({
        'student_id': student_id,
        'student_name': name,
        'parent_name': override_name or student.get('parent_name', ''),
        'parent_phone': phone,
        'parent_email': email_addr,
        'message': msg,
        'date': today,
        'alert_type': alert_type,
        'sent_by': session.get('username', 'Teacher'),
        'sent_via': sent_via,
        'status': 'sent',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

    log_notification(
        f'Parent Alert Sent — {name}',
        f'{session.get("username", "Teacher")} sent a {alert_type} alert to {name}\'s parent via {", ".join(sent_via)}.',
        type='success', role_target='admin'
    )

    return jsonify({'success': True, 'sent_via': sent_via, 'student_name': name})

@app.route('/api/alerts/delete/<alert_id>', methods=['POST'])
def delete_alert(alert_id):
    if not session.get('logged_in') or session.get('role') == 'student':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    try:
        from bson.objectid import ObjectId
        db.parent_alerts.delete_one({'_id': ObjectId(alert_id)})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/alerts/edit/<alert_id>', methods=['POST'])
def edit_alert(alert_id):
    if not session.get('logged_in') or session.get('role') == 'student':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    try:
        from bson.objectid import ObjectId
        data = request.get_json()
        new_msg = data.get('message', '').strip()
        if not new_msg:
            return jsonify({'success': False, 'error': 'Message cannot be empty'}), 400
            
        db.parent_alerts.update_one({'_id': ObjectId(alert_id)}, {'$set': {'message': new_msg}})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


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

@app.route('/api/smtp_debug')
def smtp_debug():
    """Diagnostic endpoint — shows exactly what SMTP config the app resolved.
    Accessible without login so it can be checked on Vercel without a session.
    Password is always masked. Remove this route after debugging is complete."""
    env_user = os.environ.get('MAIL_USERNAME', '(not set in env)')
    env_pass = os.environ.get('MAIL_PASSWORD', '(not set in env)')
    env_pass_masked = env_pass[:2] + '****' + env_pass[-2:] if len(env_pass) > 5 else '(short/empty)'

    try:
        db_cfg = db.settings.find_one({}, {'_id': 0}) or {}
        db_status = 'connected'
    except Exception as e:
        db_cfg = {}
        db_status = f'error: {e}'

    db_user = db_cfg.get('MAIL_USERNAME', '(not set in db.settings)')
    db_pass = db_cfg.get('MAIL_PASSWORD', '(not set in db.settings)')
    db_pass_masked = db_pass[:2] + '****' + db_pass[-2:] if len(db_pass) > 5 else '(short/empty)'
    db_server = db_cfg.get('MAIL_SERVER', '(not set in db.settings)')

    try:
        resolved = _get_smtp_config()
        resolved_pass_masked = resolved['password'][:2] + '****' + resolved['password'][-2:]
        resolved_info = {
            'server':   resolved['server'],
            'port':     resolved['port'],
            'username': resolved['username'],
            'password': resolved_pass_masked,
        }
        config_error = None
    except RuntimeError as e:
        resolved_info = {}
        config_error = str(e)

    return jsonify({
        'env_vars': {
            'MAIL_USERNAME': env_user,
            'MAIL_PASSWORD': env_pass_masked,
            'MAIL_SERVER':   os.environ.get('MAIL_SERVER', '(not set — correct, should be ignored)'),
        },
        'db_settings': {
            'status':       db_status,
            'MAIL_USERNAME': db_user,
            'MAIL_PASSWORD': db_pass_masked,
            'MAIL_SERVER':   db_server,
        },
        'resolved_config': resolved_info,
        'config_error':    config_error,
        'note': 'resolved_config shows what send_otp_email will actually use',
    })


@app.route('/api/test_smtp', methods=['POST'])
def test_smtp():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    # Resolve config the same way send_otp_email does — no hardcoded values
    try:
        cfg = _get_smtp_config()
    except RuntimeError as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    smtp_server = cfg['server']
    smtp_port   = cfg['port']
    smtp_user   = cfg['username']
    smtp_pass   = cfg['password']
    masked      = smtp_pass[:2] + '*' * (len(smtp_pass) - 4) + smtp_pass[-2:] if len(smtp_pass) > 4 else '****'

    try:
        test_email = session.get('email', smtp_user)
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=20)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)

        msg = MIMEText(
            f'SMTP test successful!\n\nServer: {smtp_server}\nUser: {smtp_user}\n\n'
            f'This confirms your email settings are working.'
        )
        msg['Subject'] = 'SMTP Test - Indus Portal'
        msg['From'] = smtp_user
        msg['To']   = test_email
        server.sendmail(smtp_user, test_email, msg.as_string())
        server.quit()

        return jsonify({
            'success': True,
            'message': f'Test email sent to {test_email}',
            'using_server': smtp_server,
            'using_user':   smtp_user,
            'using_pass':   masked,
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error':        str(e),
            'using_server': smtp_server,
            'using_user':   smtp_user,
            'using_pass':   masked,
        }), 500


@app.errorhandler(Exception)
def handle_exception(e):
    from werkzeug.exceptions import HTTPException
    # Pass through HTTP errors
    if isinstance(e, HTTPException):
        return e

    if isinstance(e, Exception):
        error_type = type(e).__name__
        error_msg = str(e)
        tb = traceback.format_exc()
        
        url = request.url if request else "Unknown URL"
        method = request.method if request else "Unknown Method"
        user = session.get('email', 'Guest') if session else "Unknown"
        
        full_details = f"User: {user}\nMethod: {method}\nURL: {url}\n\nError: {error_type} - {error_msg}\n\nTraceback:\n{tb}"
        print(f"\n--- [CRITICAL ERROR] ---\n{full_details}\n-----------------------\n")
        
        # Send async so it doesn't block the response (DISABLED to stop email spam)
        # threading.Thread(target=send_error_email, args=(full_details,)).start()
        
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
    socketio.run(app, host='0.0.0.0', debug=True, port=5000)
