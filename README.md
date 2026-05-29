# Indus Portal - Student Management Dashboard

A comprehensive web-based student management dashboard built with Flask and MongoDB. The Indus Portal provides educators and administrators with a centralized platform to manage student records, track attendance, monitor performance analytics, and communicate via integrated notifications. It also features an AI-powered Mentor assistant using Google's Gemini API.

## Features

- **Authentication & Security**
  - Secure login and registration with email-based OTP verification.
  - Password reset functionality.
- **Student Management**
  - Add, edit, and delete student records.
  - Bulk import and export of student data via CSV.
  - Generate and view digital student ID cards.
- **Attendance Tracking**
  - Daily attendance marking (Present, Absent, Late).
  - Automated low-attendance alerts sent to parents/guardians via SMS (Twilio) or Email (SendGrid).
- **Analytics & Reporting**
  - Dashboard with visual analytics for student performance and attendance.
  - Breakdown by class, board, and subjects.
- **Dashboard AI Mentor**
  - Integrated AI assistant powered by Gemini.
  - Provides quick insights and actionable suggestions based on student data.

## Technology Stack

- **Backend:** Python, Flask, PyMongo
- **Database:** MongoDB
- **Authentication:** Werkzeug Security, Flask-Mail (SMTP)
- **AI Integration:** Google Generative AI (Gemini)
- **Notifications:** Twilio (SMS), SendGrid (Email)
- **Frontend:** HTML, CSS, JavaScript (via Flask Templates)

## Setup & Installation

### Prerequisites

- Python 3.x
- MongoDB (running locally or a remote cluster)
- API Keys for Google Gemini, Twilio, and SendGrid (optional, for full functionality)

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd student_dashboard
   ```

2. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory and add the necessary environment variables:
   ```env
   MONGO_URI=mongodb://localhost:27017/
   GEMINI_API_KEY=your_gemini_api_key
   TWILIO_ACCOUNT_SID=your_twilio_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TWILIO_PHONE_NUMBER=your_twilio_phone
   SENDGRID_API_KEY=your_sendgrid_api_key
   SENDGRID_FROM_EMAIL=your_sendgrid_email
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```
   *If using flask run:*
   ```bash
   flask run
   ```

6. **Access the application:**
   Open your browser and navigate to `http://127.0.0.1:5000/`.

## Project Structure

- `app.py`: Main Flask application file containing all routes and logic.
- `requirements.txt`: Python dependencies.
- `templates/`: HTML templates for the frontend.
- `static/`: Static files (CSS, JS, images, uploads).
- `data/`: Directory for data storage/backups.
- `migrate_to_mongo.py`: Script to migrate legacy data to MongoDB.

## License

This project is licensed under the MIT License.
