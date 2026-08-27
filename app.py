"""Vercel and local entry point. The Flask app lives in backend/app.py."""
from backend.app import app, socketio, db, mail, send_otp_email
from flask_mail import Message  # re-exported for existing tests

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() in ('1', 'true', 'yes')
    try:
        socketio.run(app, host='0.0.0.0', debug=debug, port=port)
    except OSError as e:
        print(f"[SERVER ERROR] Could not bind to port {port} ({e}). Retrying on port 5001...")
        try:
            socketio.run(app, host='0.0.0.0', debug=debug, port=5001)
        except Exception as ex:
            print(f"[FATAL SERVER ERROR] Failed to start server on fallback port: {ex}")
    except Exception as e:
        print(f"[FATAL SERVER ERROR] Unexpected server error: {e}")
