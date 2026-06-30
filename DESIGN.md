# Indus Portal — System Design Document

**Project:** Indus Portal (Student Management Dashboard)
**Version:** 1.0
**Date:** June 2026

---

## 1. System Architecture Overview

Indus Portal is a monolithic Flask web application deployed as a serverless function on Vercel. All business logic, routing, and rendering live in a single `app.py` file. The frontend is server-rendered HTML using Jinja2 templates with Tailwind CSS for styling. MongoDB Atlas serves as the sole data store, also handling file storage via GridFS.

```
┌─────────────────────────────────────────────────────────┐
│                        Browser                          │
│           (Tailwind CSS + Vanilla JS + Jinja2)          │
└────────────────────────┬────────────────────────────────┘
                         │  HTTP
┌────────────────────────▼────────────────────────────────┐
│                  Vercel Serverless                       │
│                  Flask (app.py)                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │   Routes    │  │  Auth/Session│  │  Role/Perms   │  │
│  │  (50+ URLs) │  │  (Flask)     │  │  (MongoDB)    │  │
│  └──────┬──────┘  └──────────────┘  └───────────────┘  │
└─────────┼───────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────┐
│                   MongoDB Atlas                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ students │ │  users   │ │attendance│ │ gridfs   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │materials │ │  grades  │ │timetable │ │ settings │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │announce- │ │notificat-│ │assign-   │ │daily_logs│  │
│  │  ments   │ │  ions    │ │  ments   │ └──────────┘  │
│  └──────────┘ └──────────┘ └──────────┘               │
└─────────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────┐
│                 External Services                       │
│   Gemini API    │   Twilio SMS   │   SendGrid Email     │
│   Office365 SMTP                                        │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Language | Python 3.x | Single-file backend |
| Web Framework | Flask 3.0 | Jinja2 templating |
| Database | MongoDB (PyMongo) | Atlas free tier |
| File Storage | MongoDB GridFS | Photos, PDFs, logos |
| Auth | Flask sessions + Werkzeug | Server-side sessions |
| Email | smtplib (STARTTLS) + Flask-Mail | Office365 SMTP |
| SMS | Twilio Python SDK | Low-attendance alerts |
| Email (alerts) | SendGrid SDK | Fallback for SMS |
| AI | Google Generative AI SDK | Gemini 2.5 Flash |
| Frontend CSS | Tailwind CSS (CDN) | Dark mode via class strategy |
| Frontend JS | Vanilla JS | No framework |
| Hosting | Vercel | Serverless Python |
| Font | Inter (Google Fonts CDN) | |

---

## 3. Project Structure

```
student_dashboard/
├── app.py                  # Entire backend — all routes, models, helpers
├── .env                    # Environment variables (never committed)
├── requirements.txt        # Python dependencies
├── vercel.json             # Vercel deployment config
│
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Layout shell: sidebar, topbar, notifications
│   ├── login.html          # Unified login (admin/teacher/student tabs)
│   ├── signup.html         # Registration (teacher/student)
│   ├── verify_otp.html     # OTP verification
│   ├── forgot_password.html
│   ├── reset_password.html
│   ├── dashboard.html      # Teacher: student roster + analytics
│   ├── admin_dashboard.html # Admin: user activity + files + role mgmt
│   ├── admin_portal.html   # Standalone admin login page
│   ├── admin_profile.html  # Admin/teacher profile editor
│   ├── student_profile.html # Student detail view + AI chat
│   ├── profile_form.html   # Add/edit student record
│   ├── id_card.html        # Printable student ID card
│   ├── attendance.html     # Teacher attendance marking
│   ├── gradebook.html      # Teacher gradebook grid
│   ├── student_gradebook.html
│   ├── materials.html      # Teacher material upload/manage
│   ├── student_materials.html
│   ├── teacher_timetable.html
│   ├── student_timetable.html
│   ├── assignments.html    # Teacher + student assignment views
│   ├── teacher_daily_logs.html
│   ├── student_daily_logs.html
│   ├── parent_portal.html
│   ├── reports.html        # Admin analytics charts
│   ├── ai_box.html         # Standalone AI Insights page
│   ├── settings.html       # Admin system settings
│   └── staff_management.html
│
├── static/
│   ├── images/logo.png
│   └── uploads/            # Legacy local uploads (migrated to GridFS)
│
├── data/                   # Seed / backup data files
│   ├── students.json
│   ├── attendance.json
│   ├── users.json
│   └── smtp_config.json
│
└── (migration scripts)
    ├── migrate_to_mongo.py  # SQLite + JSON → MongoDB
    ├── migrate_gridfs.py    # Static files → GridFS
    └── sync_to_atlas.py     # Local MongoDB → Atlas
```

---

## 4. Database Design

All collections live in a single MongoDB database named `kalmeshwar`.

### 4.1 `students`
Stores student academic profiles. One document per student.

```json
{
  "id": "IND001",
  "name": "Rakesh",
  "dob": "2008-05-10",
  "age": "15",
  "gender": "Male",
  "blood_group": "B+",
  "email": "rakesh@gmail.com",
  "phone": "9876543210",
  "board": "State Board",
  "student_class": "10th",
  "division": "A",
  "academic_year": "2026",
  "roll_number": "21",
  "parent_name": "Vinod Kumar",
  "relationship": "Father",
  "parent_phone": "9876543210",
  "parent_email": "vinod@gmail.com",
  "occupation": "Engineer",
  "address": "Street No. 4",
  "city": "Bangalore",
  "state": "Karnataka",
  "pincode": "560001",
  "photo_url": "/file/<gridfs_id>",
  "attendance": "92",
  "performance": "85",
  "subjects": {
    "Math": 97,
    "English": 76,
    "Science": 93
  },
  "password": "raw_or_hashed"
}
```

**Key design notes:**
- `id` is the application-level key, not `_id`. Format: `IND` + zero-padded 3-digit number.
- `attendance` and `performance` are stored as strings (legacy design).
- `subjects` is a flexible key-value dict — subject names are not fixed.
- `photo_url` points to a GridFS file URL (`/file/<ObjectId>`).

### 4.2 `users`
Stores teacher accounts. One document per teacher.

```json
{
  "_id": ObjectId,
  "first_name": "Priya",
  "last_name": "Sharma",
  "email": "priya@indusschool.com",
  "password": "hashed_or_plain",
  "verified": true,
  "custom_role": "coordinator",
  "photo_url": "/file/<gridfs_id>",
  "phone": "9876500001",
  "department": "Science",
  "bio": "Senior science teacher",
  "last_active": "2026-06-11 10:30:00"
}
```

**Key design notes:**
- `verified` must be `true` before login is permitted.
- `custom_role` is optional. If absent, the account behaves as a default teacher.
- `last_active` is updated on every authenticated request via `@app.before_request`.

### 4.3 `student_users`
Auth-only collection for students. Separated from profiles to allow clean credential management.

```json
{
  "_id": ObjectId,
  "student_id": "IND001",
  "email": "rakesh@gmail.com",
  "password": "plain_or_hashed",
  "last_active": "2026-06-11 10:30:00"
}
```

### 4.4 `admins`
Stores admin accounts.

```json
{
  "_id": ObjectId,
  "email": "kalmeshwargurav1028@gmail.com",
  "password": "Kalmeshwar@123",
  "name": "System Admin",
  "last_active": "2026-06-11 10:30:00"
}
```

**Note:** The default admin is seeded at first login if the collection is empty.

### 4.5 `attendance`
One document per school day.

```json
{
  "date": "2026-06-11",
  "records": {
    "IND001": "Present",
    "IND002": "Absent",
    "IND003": "Late"
  }
}
```

### 4.6 `grades`
One document per student-subject pair.

```json
{
  "student_id": "IND001",
  "subject": "Mathematics",
  "ca_mark": "35",
  "exam_mark": "58"
}
```

### 4.7 `assignments`

```json
{
  "_id": ObjectId,
  "title": "Chapter 5 Questions",
  "subject": "Science",
  "class_name": "10th",
  "gradebook_category": "Homework",
  "max_points": "100",
  "due_date": "2026-06-20",
  "description": "Answer all questions from Chapter 5.",
  "smart_alert_parents": true,
  "smart_pin_calendar": false,
  "created_by": "Priya Sharma",
  "submissions": [
    {
      "student_id": "IND001",
      "student_name": "Rakesh",
      "submitted_at": "2026-06-18 14:30",
      "grade": "88"
    }
  ]
}
```

### 4.8 `materials`

```json
{
  "_id": ObjectId,
  "title": "Physics Formula Sheet",
  "class": "10th",
  "subject": "Physics",
  "file_url": "/file/<gridfs_id>",
  "uploaded_at": "2026-06-10 09:00:00",
  "teacher_id": "<ObjectId>"
}
```

### 4.9 `timetable`

```json
{
  "_id": ObjectId,
  "day": "Monday",
  "time": "09:00",
  "subject": "Mathematics",
  "room": "Room 101",
  "teacher": "Priya Sharma",
  "class_name": "10th"
}
```

### 4.10 `daily_logs`

```json
{
  "_id": ObjectId,
  "date": "2026-06-11",
  "class_name": "10th",
  "subject": "Science",
  "topics": "Chapter 5: Chemical Reactions",
  "remarks": "Good class participation",
  "teacher": "Priya Sharma"
}
```

### 4.11 `announcements`

```json
{
  "_id": ObjectId,
  "title": "School Holiday Notice",
  "body": "School will be closed on June 15th.",
  "audience": "all",
  "expiry_date": "2026-06-15",
  "date_sent": "2026-06-10 08:00:00",
  "author_id": "<ObjectId>"
}
```

`audience` values: `"all"`, `"teachers"`, `"students"`

### 4.12 `notifications`

```json
{
  "_id": ObjectId,
  "title": "New Material Uploaded",
  "message": "Physics Formula Sheet has been added for 10th.",
  "type": "info",
  "role_target": "teacher",
  "read_by": ["user_id_1", "user_id_2"],
  "timestamp": "2026-06-11 09:15:00"
}
```

`type` values: `"info"`, `"success"`, `"error"`
`role_target` values: `"admin"`, `"teacher"`, `"student"`, `"all"`

### 4.13 `role_permissions`
Single document stores the permission matrix for all roles.

```json
{
  "_id": "global_config",
  "teacher": {
    "view_dashboard": true,
    "manage_students": true,
    "edit_materials": true,
    "modify_attendance": true,
    "manage_grades": true,
    "send_announcements": false,
    "ai_insights": false,
    "view_system_health": false
  },
  "coordinator": {
    "view_dashboard": true,
    "manage_students": false,
    "edit_materials": true,
    "modify_attendance": false,
    "manage_grades": false,
    "send_announcements": true,
    "ai_insights": true,
    "view_system_health": false
  }
}
```

### 4.14 `settings`
Single document for system-wide config.

```json
{
  "school_name": "Indus International School",
  "academic_year": "2025 - 2026",
  "logo_url": "/file/<gridfs_id>",
  "logo_filename": "logo.png",
  "MAIL_SERVER": "smtp.office365.com",
  "MAIL_PORT": 587,
  "MAIL_USERNAME": "agent4@indusschool.com",
  "MAIL_PASSWORD": "...",
  "GEMINI_API_KEY": "...",
  "TWILIO_ACCOUNT_SID": "...",
  "TWILIO_AUTH_TOKEN": "...",
  "TWILIO_PHONE_NUMBER": "...",
  "SENDGRID_API_KEY": "...",
  "SENDGRID_FROM_EMAIL": "..."
}
```

### 4.15 `reports`
Caches the last generated analytics snapshot.

```json
{
  "type": "latest_analytics",
  "generated_at": "2026-06-11T09:00:00",
  "students_count": 11,
  "analytics": { ... }
}
```

### 4.16 `messages`
Stores messages sent by students from the parent portal.

```json
{
  "_id": ObjectId,
  "student_id": "IND001",
  "student_name": "Rakesh",
  "subject": "Doubt in Chapter 5",
  "message": "I have a question about...",
  "date_sent": "2026-06-11 11:00",
  "status": "unread"
}
```

### 4.17 GridFS (`fs.files` / `fs.chunks`)
Binary file storage managed by PyMongo's `gridfs.GridFS`. Used for:
- Student profile photos
- Admin/teacher profile photos
- Study material files (PDFs, etc.)
- Portal logo

Files are accessed via the `/file/<file_id>` route which streams them directly from GridFS.

---

## 5. Authentication and Session Design

### 5.1 Session Schema

Flask's server-side session stores the following after a successful login:

| Key | Type | Description |
|-----|------|-------------|
| `logged_in` | bool | True if authenticated |
| `role` | string | `"admin"`, `"teacher"`, `"student"`, or custom role name |
| `user_id` | string | MongoDB `_id` (teachers/admins) or student `id` (e.g. `IND001`) |
| `username` | string | Display name |
| `email` | string | Login email |
| `photo_url` | string | Profile photo URL (optional) |

Session lifetime: 24 hours (`PERMANENT_SESSION_LIFETIME`).

### 5.2 Login Flow

```
POST /login
│
├── login_type == "admin"
│     └── Query db.admins by email → compare password (plain or hashed)
│         └── Set session role = "admin" → redirect /admin_dashboard
│
├── login_type == "student"
│     ├── Query db.student_users by email → compare password
│     │   └── Set session role = "student" → redirect /student/<id>
│     └── Fallback: query db.students by email → compare password or student_id
│
└── login_type == "teacher" (default)
      └── Query db.users by email → compare password (plain or hashed)
          ├── If not verified → generate OTP → send email → redirect /verify_otp
          └── If verified → set session role = custom_role or "teacher"
                           → redirect /dashboard
```

### 5.3 OTP Flow

```
Signup / Forgot Password
    │
    └── generate_otp() → 6-digit numeric string
        → store in session: otp_code, otp_expiry (+5 min), otp_email
        → send_otp_email() → SMTP via Office365
        → redirect to /verify_otp or /reset_password
            │
            └── POST with otp
                → verify session otp_code == submitted otp
                → verify datetime.now() < otp_expiry
                → if valid: mark verified / update password
```

### 5.4 Permission Check

Two mechanisms are used:

**Route-level check** (inline in each route):
```python
if not session.get('logged_in'):
    return redirect(url_for('login'))
if session.get('role') != 'admin':
    return redirect(url_for('login'))
```

**Feature-level check** (via `has_permission()`):
```python
def has_permission(permission_name):
    if session.get('role') == 'admin': return True
    config = db.role_permissions.find_one({'_id': 'global_config'})
    return config.get(role, {}).get(permission_name, False)
```

Permission names: `view_dashboard`, `manage_students`, `edit_materials`, `modify_attendance`, `view_system_health`, `send_announcements`, `ai_insights`, `manage_grades`

---

## 6. Application Routes

### 6.1 Auth Routes

| Method | URL | Description |
|--------|-----|-------------|
| GET/POST | `/login` | Unified login (admin / teacher / student) |
| GET/POST | `/admin-portal` | Standalone admin login |
| GET/POST | `/signup` | Register teacher or student |
| GET/POST | `/verify_otp` | OTP verification for email confirm / new login |
| GET/POST | `/forgot_password` | Request password reset |
| GET/POST | `/reset_password` | Submit new password with OTP |
| GET | `/logout` | Clear session and redirect to login |

### 6.2 Teacher/Admin Feature Routes

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` or `/dashboard` | Teacher dashboard — roster + analytics |
| GET/POST | `/profile` | Add or edit student profile |
| GET | `/student/<id>` | View student detail page |
| GET | `/student/<id>/id_card` | Printable student ID card |
| POST | `/delete/<id>` | Delete student |
| POST | `/quick_add_mark/<id>` | Add subject mark from student profile |
| GET | `/export_students` | Download students CSV |
| POST | `/import_students` | Upload CSV to bulk-import students |
| GET/POST | `/attendance` | Mark and view daily attendance |
| GET/POST | `/gradebook` | Teacher gradebook grid |
| GET | `/student/<id>/gradebook` | Student's own gradebook |
| GET/POST | `/materials` | Upload/manage study materials |
| POST | `/material/edit/<id>` | Edit a material record |
| POST | `/material/delete/<id>` | Delete material + GridFS file |
| GET/POST | `/timetable` | View/manage timetable |
| GET/POST | `/assignments` | Create/grade/view assignments |
| GET/POST | `/daily_logs` | Add/view daily class logs |
| GET/POST | `/settings` | System settings |
| GET/POST | `/profile` (admin) | Admin/teacher profile edit |
| GET | `/student/materials` | Student-facing materials list |
| GET/POST | `/parent_portal` | Parent-facing student summary |
| GET | `/reports` | Analytics and reports page |
| GET | `/ai_box` | Standalone AI Insights page |

### 6.3 Admin-Only Routes

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/admin_dashboard` | Admin dashboard |
| GET | `/staff_management` | Staff listing |
| POST | `/api/staff/add` | Add staff member |
| GET | `/super_admin_profile` | Admin's own profile |
| POST | `/super_admin_update_profile` | Update admin profile |
| POST | `/admin/reset_password` | Reset any user's password |

### 6.4 API Routes

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/analyze_student/<id>` | Gemini AI for individual student |
| POST | `/api/dashboard_ai` | Gemini AI for class-wide dashboard |
| POST | `/api/announcements` | Create announcement |
| DELETE | `/api/announcements/<id>` | Delete announcement |
| GET | `/api/notifications` | Get unread notifications for current user |
| POST | `/api/notifications/read/<id>` | Mark notification as read |
| POST | `/api/notifications/clear_all` | Mark all notifications read |
| POST | `/api/role_permissions` | Update role permission matrix |
| POST | `/api/roles/add` | Create custom role |
| DELETE | `/api/roles/<name>` | Delete custom role |
| POST | `/api/users/<id>/role` | Assign role to teacher |
| POST | `/api/test_smtp` | Send SMTP test email |
| GET | `/api/smtp_debug` | View resolved SMTP config (debug) |
| GET | `/file/<file_id>` | Stream file from GridFS |

### 6.5 Dev/Utility Routes

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/dev/wipe_users` | **Dangerous** — deletes all users with no auth check |
| GET | `/dev/test_error` | Admin-only deliberate error trigger |

---

## 7. Key Component Designs

### 7.1 Sidebar Navigation

The sidebar is rendered in `base.html` and is conditionally shown only for logged-in users. Navigation items are rendered using Jinja2 conditionals based on:

- `session.get('role')` — controls top-level sections (admin vs teacher vs student)
- `role_permissions` context variable — injected by `@app.context_processor` — controls feature-level items

The sidebar collapses to icon-only mode on toggle (JS-driven class swap between `w-64` and `w-20`).

### 7.2 Notification System

```
Every 5 min (300s) in production:
    Frontend JS → GET /api/notifications
        → Returns up to 10 unread notifications for user's role
        → Badge count updates
        → Dropdown renders notification cards

User dismisses:
    POST /api/notifications/read/<id>
        → $addToSet read_by: [user_id]

User clears all:
    POST /api/notifications/clear_all
        → $addToSet read_by: [user_id] for all matching docs
```

Notifications are never deleted — they are soft-dismissed by adding the user's ID to `read_by`. Error-type notifications are excluded from the bell display.

### 7.3 Attendance Calculation

After each attendance save, `recalculate_students_attendance()` is called synchronously:

```
For each student:
    total_days = count of all attendance docs where student_id exists
    days_present = sum:
        Present → +1.0
        Late    → +0.5
        Absent  → +0.0
    percentage = round((days_present / total_days) * 100, 1)
    → write back to db.students[student_id].attendance
```

**Performance note:** This is O(students × attendance_docs) and runs synchronously on every save. At scale this will become slow and should be moved to a background task.

### 7.4 File Storage (GridFS)

All file uploads follow this pattern:

```python
# Upload
file_id = fs.put(file_object, filename=unique_name, content_type=mime_type)
file_url = url_for('get_file', file_id=str(file_id))

# Retrieve (route)
@app.route('/file/<file_id>')
def get_file(file_id):
    file = fs.get(ObjectId(file_id))
    return send_file(io.BytesIO(file.read()), mimetype=file.content_type, ...)

# Delete
fs.delete(ObjectId(file_id))
```

File URLs are stored as `/file/<ObjectId>` strings in their respective collection documents.

### 7.5 SMTP Configuration Resolution

SMTP config is resolved with a deliberate priority scheme to prevent Vercel's cached environment variables from overriding intended server settings:

```
_get_smtp_config():
  username → env MAIL_USERNAME  OR  db.settings.MAIL_USERNAME
  password → env MAIL_PASSWORD  OR  db.settings.MAIL_PASSWORD
  server   → db.settings.MAIL_SERVER  OR  "smtp.office365.com"  (NEVER from env)
  port     → db.settings.MAIL_PORT    OR  587                   (NEVER from env)
```

This is intentional — the `MAIL_SERVER` env var is explicitly ignored because Vercel deployments may carry a stale Gmail value.

### 7.6 AI Integration (Gemini)

```
configure_gemini():
    api_key = db.settings.GEMINI_API_KEY OR env.GEMINI_API_KEY
    return genai.Client(api_key=api_key), api_key

POST /api/analyze_student/<id>:
    student = db.students.find_one(id)
    client, key = configure_gemini()
    if not key: return fallback message
    prompt = system_prompt + student data + teacher's question
    response = client.models.generate_content(model='gemini-2.5-flash', ...)
    return response.text (with * stripped)

POST /api/dashboard_ai:
    students = db.students.find()
    → compute: total, low_attendance_list, high_performers_list
    → build system_prompt with aggregated data
    → call Gemini → return 3-sentence response
```

The AI is stateless — no conversation history is stored server-side. The chat UI accumulates messages client-side only.

---

## 8. Frontend Design

### 8.1 Layout

All pages extend `base.html`, which provides:
- Collapsible green sidebar (`bg-[#2563eb]`) with role-gated navigation links
- Top header bar with: notification bell, page title, username, profile avatar
- Flash message area (blue-themed alert banners)
- Main scrollable content area

### 8.2 Color Palette

| Usage | Color |
|-------|-------|
| Primary / Sidebar | Blue (`#2563eb`) |
| Sidebar hover / accent | Blue-600 |
| Admin dashboard accent | Red / Rose |
| Teacher dashboard accent | Blue / Indigo |
| Student accent | Purple / Fuchsia |
| Success states | Blue-100 / Green-100 |
| Warning states | Yellow-100 |
| Danger states | Red-100 |
| Background | Gray-50 with dot-grid pattern |
| Dark mode background | Gray-900 |

### 8.3 Page-by-Page Summary

**Login (`login.html`)** — Three tabs: Admin, Teacher, Student. Each tab shows relevant input fields. Built with standard form POST.

**Dashboard (`dashboard.html`)** — Teacher view. Analytics summary cards at top. Data management (import/export CSV). Filterable student roster table (search by name, filter by class and division) with JS-driven live filtering and autocomplete dropdown.

**Student Profile (`student_profile.html`)** — Photo, stats badges (performance, attendance), contact details, subjects with progress bars, attendance history table, AI Mentor chat panel (WebSocket-style fetch loop), teacher contact directory with mailto links.

**Admin Dashboard (`admin_dashboard.html`)** — User activity stats cards, three activity tables (admins, teachers, students) with active/inactive status, plaintext password display, password reset modals, file listing, role permissions matrix (checkbox grid), announcements management.

**Attendance (`attendance.html`)** — Date picker, per-student radio buttons (Present / Absent / Late), daily stats bar, date history sidebar.

**Gradebook (`gradebook.html`)** — Grid table: students as rows, subjects as columns, CA and exam mark inputs per cell. Inline form submission.

**Materials (`materials.html`)** — Upload form (title, class, subject, file), cards list of uploaded materials with edit and delete modals.

**Timetable** — Two templates (`teacher_timetable.html`, `student_timetable.html`): weekly grid organized by day, current day highlighted.

**Assignments (`assignments.html`)** — Teacher: creation form + list with submission counts + grading per student. Student: list with status badges (pending/submitted/overdue), days-left countdown.

**Settings (`settings.html`)** — Left nav tabs (General, Academic Setup, Alert Thresholds, Access Control). Right panel: school name, logo upload, academic year, SMTP credentials, Gemini key, Twilio credentials, SendGrid credentials. Test SMTP button.

**Reports (`reports.html`)** — Chart.js (or similar) charts: board distribution (pie), class performance (bar), subject averages (bar). Exportable data.

**AI Box (`ai_box.html`)** — Full-page AI chat interface connected to `/api/dashboard_ai`.

### 8.4 JavaScript Patterns

All JS is vanilla (no framework). Common patterns used:

- **Fetch API** for all AJAX calls (AI chat, notifications, role updates, announcements)
- **`document.addEventListener('DOMContentLoaded', ...)`** for DOM initialization
- **Polling** with `setInterval` for notification refresh (every 5 minutes)
- **Confirm dialogs** for destructive actions (student delete, material delete)
- **Live table filtering** on the dashboard roster using `data-*` attributes

---

## 9. Deployment Design

### 9.1 Vercel Serverless

`vercel.json` routes all traffic to `app.py`:

```json
{
  "version": 2,
  "builds": [{ "src": "app.py", "use": "@vercel/python" }],
  "routes": [{ "src": "/(.*)", "dest": "app.py" }]
}
```

Each HTTP request spins up a new serverless function instance. Because of this:
- No persistent in-memory state between requests
- No local filesystem writes (hence GridFS for all file storage)
- MongoDB connection pool capped at `maxPoolSize=1` to avoid exhausting Atlas free-tier connection limits across many concurrent instances

### 9.2 Environment Variables

Set in Vercel dashboard and locally in `.env`:

| Variable | Required | Notes |
|----------|----------|-------|
| `MONGO_URI` | Yes | Atlas connection string |
| `SECRET_KEY` | Yes | Flask session signing key |
| `MAIL_USERNAME` | Yes | Office365 SMTP username |
| `MAIL_PASSWORD` | Yes | Office365 SMTP password |
| `GEMINI_API_KEY` | Optional | AI features disabled if absent |
| `TWILIO_ACCOUNT_SID` | Optional | SMS alerts disabled if absent |
| `TWILIO_AUTH_TOKEN` | Optional | SMS alerts disabled if absent |
| `TWILIO_PHONE_NUMBER` | Optional | SMS alerts disabled if absent |
| `SENDGRID_API_KEY` | Optional | Email alerts disabled if absent |
| `SENDGRID_FROM_EMAIL` | Optional | Email alerts disabled if absent |

### 9.3 Local Development

```bash
pip install -r requirements.txt
# create .env with variables above
python app.py          # runs on http://localhost:5000
```

### 9.4 Data Migration Path

For moving data between environments:

```
JSON files → migrate_to_mongo.py → Local MongoDB
                                        ↓
                               sync_to_atlas.py → MongoDB Atlas

Static uploads → migrate_gridfs.py → GridFS (Atlas)
```

---

## 10. Security Design

### 10.1 Current Implementation

| Concern | Implementation |
|---------|---------------|
| Session auth | `session.get('logged_in')` checked on every protected route |
| Role enforcement | `session.get('role')` checked for admin/student separation |
| Feature permissions | `has_permission()` reads from `db.role_permissions` |
| File upload safety | `werkzeug.utils.secure_filename` + UUID prefix |
| OTP expiry | 5-minute TTL stored in session |
| Password hashing | Partial — `generate_password_hash` used in reset flow; signup stores plain |

### 10.2 Known Security Issues

These are documented here for remediation tracking:

1. **Plaintext passwords in admin UI** — `admin_dashboard.html` renders `{{ t.password }}` directly. Must be removed.
2. **Inconsistent password hashing** — Teacher signup stores plaintext. Login accepts both plain and hashed via `check_password_hash` fallback. Needs standardization.
3. **Unauthenticated `/dev/wipe_users`** — No login check. Deletes entire database. Must be deleted before any public deployment.
4. **`SECRET_KEY` default** — Falls back to `'super_secret_key_change_in_production'` if env var not set. Must be overridden.
5. **No CSRF protection** — Flask forms have no CSRF tokens. Standard Flask-WTF or a custom token should be added.
6. **API credentials in `db.settings`** — Gemini key, Twilio tokens, and SMTP password are stored in MongoDB in plaintext. If the database is compromised, all credentials are exposed.

---

## 11. Error Handling

All unhandled exceptions are caught by a global `@app.errorhandler(Exception)` handler that:

1. Formats a full traceback with user, URL, method, and error details
2. Logs the error as a notification in `db.notifications` (type: `"error"`)
3. Returns a plain 500 HTML page to the user
4. **Does not send email alerts** (disabled via code comment to prevent spam)

HTTP exceptions (4xx) are passed through unchanged by the handler.

A `/dev/test_error` route (admin-only) deliberately raises a `ValueError` to verify the error handler works.
