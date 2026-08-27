# Indus Portal — Project Requirements Document

**Project:** Indus Portal (Student Management Dashboard)
**Version:** 1.0
**Date:** June 2026
**Status:** Active / In Production

---

## 1. Project Overview

Indus Portal is a web-based school management system built for Indus International School. It provides a centralized platform for administrators, teachers, and students to manage academic records, track attendance, communicate, and view analytics. The system is deployed on Vercel and backed by MongoDB Atlas.

---

## 2. Stakeholders and User Roles

### 2.1 Admin
The system administrator. Has full unrestricted access to every feature and all data.

### 2.2 Teacher
A registered staff member. Has access to student management, attendance, gradebook, materials, timetable, assignments, and daily logs. Specific permissions can be restricted by admin via role management.

### 2.3 Custom Roles
Admin can create named roles (e.g., "coordinator", "counselor") and assign them fine-grained permissions from a fixed set of capabilities. These are assigned to teacher accounts.

### 2.4 Student
A registered learner. Has a read-only view of their own profile, grades, attendance, materials, timetable, assignments, daily logs, and a parent connect portal.

---

## 3. Functional Requirements

### 3.1 Authentication

| ID | Requirement |
|----|-------------|
| AUTH-01 | Users must be able to register accounts for teacher and student roles via a signup form. |
| AUTH-02 | Teacher registration must trigger an OTP email for email verification before the account is activated. |
| AUTH-03 | Unverified teacher accounts must not be able to log in. |
| AUTH-04 | The system must support three login types from a single login page: Admin, Teacher, and Student. |
| AUTH-05 | Admin login must be accessible through a dedicated `/admin-portal` route in addition to the main login. |
| AUTH-06 | Student login must accept email + password or email + student ID. |
| AUTH-07 | The system must provide a "forgot password" flow that sends a time-limited (5-minute) OTP reset code to the user's email. |
| AUTH-08 | OTP codes must expire after 5 minutes. |
| AUTH-09 | Sessions must persist for 24 hours. |
| AUTH-10 | On logout, all session data must be cleared. |

### 3.2 Student Management

| ID | Requirement |
|----|-------------|
| STU-01 | Teachers and admins must be able to create full student profiles including: name, DOB, age, gender, blood group, photo, contact details, parent/guardian details, address, board, class, division, academic year, roll number, and subjects with scores. |
| STU-02 | Photos must be stored in MongoDB GridFS, not on the local filesystem. |
| STU-03 | Student IDs must be auto-generated in the format `IND001`, `IND002`, etc., incrementing sequentially. |
| STU-04 | Existing student records must be editable. |
| STU-05 | Students must be deletable by teachers and admins. |
| STU-06 | Teachers must be able to add individual subject marks to a student directly from their profile. |
| STU-07 | The student roster must be searchable by name and filterable by class and division. |
| STU-08 | Student records must be exportable as CSV files, optionally filtered by class. |
| STU-09 | Student records must be bulk-importable via CSV upload with auto-generated IDs. |
| STU-10 | Each student must have a printable digital ID card view. |

### 3.3 Attendance

| ID | Requirement |
|----|-------------|
| ATT-01 | Teachers and admins (with permission) must be able to mark daily attendance for all students. |
| ATT-02 | Attendance statuses must be: Present, Absent, or Late. |
| ATT-03 | Late attendance must count as 0.5 days for percentage calculations. |
| ATT-04 | Attendance records must be stored per date, keyed by student ID. |
| ATT-05 | After each attendance save, the system must recalculate and update each student's cumulative attendance percentage. |
| ATT-06 | The attendance page must allow navigation to previous dates. |
| ATT-07 | A daily summary (total present, absent, late, percentage) must be displayed on the attendance page. |
| ATT-08 | When a student is marked Absent and their cumulative attendance drops below 75%, the system must send an alert to the parent/guardian via SMS (Twilio) if a phone number is on file, or via email (SendGrid) as a fallback. |

### 3.4 Gradebook

| ID | Requirement |
|----|-------------|
| GRD-01 | Teachers and admins (with permission) must be able to enter CA (continuous assessment) marks and exam marks per student per subject. |
| GRD-02 | The gradebook must display all students and all subjects in a grid. |
| GRD-03 | Students must be able to view their own gradebook with total scores calculated per subject. |

### 3.5 Assignments

| ID | Requirement |
|----|-------------|
| ASN-01 | Teachers must be able to create assignments with: title, subject, class, gradebook category, max points, due date, and description. |
| ASN-02 | Assignments can optionally trigger smart alerts to parents and pin to the calendar. |
| ASN-03 | Students must be able to submit (mark as submitted) their assignments. |
| ASN-04 | Teachers must be able to grade individual student submissions. |
| ASN-05 | Students must see assignment status: pending, submitted, or overdue, with days remaining. |
| ASN-06 | Teachers must be able to delete assignments. |

### 3.6 Study Materials

| ID | Requirement |
|----|-------------|
| MAT-01 | Teachers and admins (with permission) must be able to upload study materials with a title, class, and subject. |
| MAT-02 | Uploaded files must be stored in MongoDB GridFS. |
| MAT-03 | On material upload, the system must email all students in the target class to notify them of the new material. |
| MAT-04 | Teachers must be able to edit and delete materials. Deleting a material must also delete the file from GridFS. |
| MAT-05 | Students must be able to view materials uploaded for their class. |

### 3.7 Timetable

| ID | Requirement |
|----|-------------|
| TT-01 | Teachers must be able to add and delete timetable entries with: day, time, subject, room, and class. |
| TT-02 | Teachers must see their own timetable filtered by their name. |
| TT-03 | Students must see the timetable for their class. |
| TT-04 | The timetable must be organized by day of week and sorted by time. |
| TT-05 | The current day must be highlighted. |

### 3.8 Daily Logs

| ID | Requirement |
|----|-------------|
| LOG-01 | Teachers must be able to add daily log entries with: date, class, subject, topics covered, and remarks. |
| LOG-02 | Students must be able to view logs for their class (read-only). |
| LOG-03 | Logs must be displayed in reverse chronological order. |

### 3.9 Parent Portal

| ID | Requirement |
|----|-------------|
| PAR-01 | Students must be able to access a parent-facing view of their academic summary. |
| PAR-02 | The parent portal must show recent assignments (with grades where available) and recent daily logs. |
| PAR-03 | Students (on behalf of parents) must be able to send a message to teachers via the portal. |

### 3.10 Reports and Analytics

| ID | Requirement |
|----|-------------|
| RPT-01 | The teacher dashboard must display analytics: total students, average attendance, average performance, present/absent counts, class distribution, and board distribution. |
| RPT-02 | The reports page must provide deeper analytics: performance by class, performance by subject, and board distribution. |
| RPT-03 | Analytics charts must be rendered visually (using a charting library). |
| RPT-04 | Reports must be auto-saved to the database on each generation. |

### 3.11 AI Insights (Gemini Integration)

| ID | Requirement |
|----|-------------|
| AI-01 | Each student profile must include an embedded AI Mentor chat panel. |
| AI-02 | The AI must receive the student's performance score and attendance as context and provide actionable suggestions. |
| AI-03 | The teacher dashboard must include a Dashboard AI assistant that provides class-wide insights. |
| AI-04 | A dedicated AI Insights page must be available (gated by role permission). |
| AI-05 | If the Gemini API key is not configured, all AI endpoints must respond with a graceful fallback message and not crash. |
| AI-06 | The Gemini API key must be configurable from the Settings page or via environment variable. |

### 3.12 Admin Dashboard

| ID | Requirement |
|----|-------------|
| ADM-01 | The admin dashboard must display user activity stats: total and active counts for admins, teachers, and students (active = last seen within 15 minutes). |
| ADM-02 | The admin dashboard must list all users (admins, teachers, students) with their last active time, status, and password (plaintext display — see security notes). |
| ADM-03 | Admins must be able to reset passwords for teacher and student accounts. |
| ADM-04 | The admin dashboard must display a list of all uploaded materials with links. |
| ADM-05 | Admins must be able to create and send announcements to target audiences: All, Teachers, or Students. |
| ADM-06 | Announcements must have an expiry date; expired announcements must not appear in the sidebar. |
| ADM-07 | Admins must be able to delete announcements. |
| ADM-08 | Admins must be able to view and manage GridFS storage usage. |

### 3.13 Role Management

| ID | Requirement |
|----|-------------|
| ROL-01 | Admins must be able to create custom roles with arbitrary names. |
| ROL-02 | Admins must be able to assign each role a permission matrix over: View Dashboard, Manage Students, Edit Materials, Modify Attendance, View System Health, Send Announcements, AI Insights, Manage Grades. |
| ROL-03 | Admins must be able to assign custom roles to individual teacher accounts. |
| ROL-04 | Admins must be able to delete custom roles. Deleting a role must reset affected users back to the default teacher role. |
| ROL-05 | Admin role must always have all permissions and cannot be modified. |

### 3.14 Notifications

| ID | Requirement |
|----|-------------|
| NOT-01 | The system must support an in-app notification system visible in the top navbar as a bell icon with a badge count. |
| NOT-02 | Notifications must be targeted by role (admin, teacher, student, or all). |
| NOT-03 | Users must be able to dismiss individual notifications or clear all at once. |
| NOT-04 | Notifications must be polled from the server periodically (every 5 minutes in production). |
| NOT-05 | Key system events (role changes, announcements, material uploads, settings updates, errors) must generate notifications. |

### 3.15 System Settings

| ID | Requirement |
|----|-------------|
| SET-01 | Admins must be able to configure school name, portal logo, and academic year. |
| SET-02 | All API credentials (SMTP email/password, Gemini API key, Twilio credentials, SendGrid credentials) must be configurable from the Settings page. |
| SET-03 | Settings must be stored in the database and take precedence over environment variables for server and port, but environment variables take precedence for credentials. |
| SET-04 | Admins must be able to test SMTP configuration by sending a test email directly from the Settings page. |

### 3.16 User Profiles

| ID | Requirement |
|----|-------------|
| PRF-01 | Admins and teachers must be able to update their profile: name, phone, department, bio, and profile photo. |
| PRF-02 | Profile photos must be stored in GridFS. |
| PRF-03 | Profile information must be reflected in the session and the top navbar on update. |

---

## 4. Non-Functional Requirements

### 4.1 Performance
- MongoDB connection pool must be limited to 1 connection (maxPoolSize=1) to stay within the free-tier Atlas connection limit (~500 connections), supporting Vercel's serverless deployment model.
- API responses for AI endpoints should be fast enough for use in a chat-style UI.

### 4.2 Availability
- The system must be deployable to Vercel as a serverless Python application.
- The system must also run locally using `python app.py`.

### 4.3 Security
- Passwords for new accounts should be hashed using Werkzeug's `generate_password_hash`.
- OTP codes must be session-bound and expire after 5 minutes.
- All protected routes must check `session.get('logged_in')` and redirect unauthenticated users to login.
- Role-gated routes must verify `session.get('role')` before rendering.
- File uploads must use `secure_filename` and unique prefixes to prevent path traversal.
- **Known Issue:** The admin dashboard currently displays plaintext passwords for all user types. This is a significant security risk and should be addressed (see open issues).
- **Known Issue:** There is a `/dev/wipe_users` endpoint with no authentication that destroys all user data.

### 4.4 Storage
- All user-uploaded files (photos, materials, logos) must be stored in MongoDB GridFS, not on the local filesystem. This is required for Vercel compatibility (no persistent disk).

### 4.5 Email
- SMTP must use Office365 (smtp.office365.com:587 with STARTTLS) as the default server.
- The SMTP server and port must never be read from environment variables to prevent accidental routing to Gmail or other providers.
- Credentials are loaded from environment variables first, with database settings as fallback.

### 4.6 Usability
- The UI must use Tailwind CSS (via CDN) with the Inter font.
- The layout must be responsive with a collapsible sidebar.
- The sidebar must render only the navigation items that the current user's role has permission to see.
- Dark mode must be supported via Tailwind's `class` dark mode strategy.

---

## 5. External Integrations

| Service | Purpose | Configuration |
|---------|---------|---------------|
| MongoDB Atlas | Primary database + GridFS file storage | `MONGO_URI` env var |
| Google Gemini (gemini-2.5-flash) | AI mentor and dashboard AI assistant | `GEMINI_API_KEY` |
| Twilio | SMS alerts for low student attendance | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` |
| SendGrid | Email alerts for low attendance (SMS fallback) | `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL` |
| Office365 SMTP | OTP emails, material upload notifications, password reset | `MAIL_USERNAME`, `MAIL_PASSWORD` |
| Vercel | Serverless hosting | `vercel.json` routing config |

---

## 6. Data Requirements

### 6.1 Student Profile Fields
`id`, `name`, `dob`, `age`, `gender`, `blood_group`, `email`, `phone`, `board`, `student_class`, `division`, `academic_year`, `roll_number`, `parent_name`, `relationship`, `parent_phone`, `parent_email`, `occupation`, `address`, `city`, `state`, `pincode`, `photo_url`, `attendance` (%), `performance` (score), `subjects` (dict: subject → score), `password`

### 6.2 Teacher/Staff Fields
`first_name`, `last_name`, `email`, `password`, `verified`, `custom_role`, `photo_url`, `phone`, `department`, `bio`, `last_active`

### 6.3 Attendance Record
Per-date document: `date` (YYYY-MM-DD), `records` (dict: student_id → "Present" | "Absent" | "Late")

### 6.4 Assignment Fields
`title`, `subject`, `class_name`, `gradebook_category`, `max_points`, `due_date`, `description`, `smart_alert_parents`, `smart_pin_calendar`, `created_by`, `submissions` (array of: `student_id`, `student_name`, `submitted_at`, `grade`)

### 6.5 Material Fields
`title`, `class`, `subject`, `file_url`, `uploaded_at`, `teacher_id`

### 6.6 Announcement Fields
`title`, `body`, `audience` (all | teachers | students), `expiry_date`, `date_sent`, `author_id`

### 6.7 Notification Fields
`title`, `message`, `type` (info | success | error), `role_target`, `read_by` (array of user IDs), `timestamp`

---

## 7. Open Issues and Known Gaps

1. **Security — Plaintext Passwords Displayed**: The admin dashboard renders plaintext passwords for all users in the HTML. This should be removed immediately in production.
2. **Security — Unauthenticated Wipe Endpoint**: `/dev/wipe_users` permanently deletes all data without any authentication check. Must be removed before production use.
3. **Password Hashing Inconsistency**: Some flows store passwords in plaintext; others use `generate_password_hash`. All password storage must be standardized to use hashing.
4. **`/dev/test_error` Route**: This route is accessible to admins and triggers a deliberate crash for testing. Should be removed or heavily restricted.
5. **Timetable Student View**: Students see timetable based on `student_class`; teachers see based on username match. If a teacher's username doesn't match the timetable's `teacher` field exactly, entries are missed.
6. **Mock Data in Student Profile**: Marks and attendance history are randomly generated if not present in the database. This mock data is returned from the API and displayed as real data.
7. **Staff Management Page**: The `/staff_management` route fetches staff by role field (`teacher` | `admin`), but the signup flow does not set a `role` field — it only sets `verified`. This means the staff management page may display no users.
8. **`add_staff` API**: References `bcrypt` which is not imported and not in `requirements.txt`. This endpoint will crash if called.
9. **Error emails are permanently disabled** via a code comment. The system logs to the notification DB instead, but there is no admin alert for production errors beyond the notification bell.
