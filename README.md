# HostelCare — PTSS Hostel Facility Reporting App

A Flask + HTML + CSS web application based on the supplied Figma mini-project. It includes a welcome page, account registration/login, a report dashboard, report submission, report list filters, report details, and staff status updates.

## Requirements
- Python 3.10+
- pip

## Run on Windows
1. Extract this folder.
2. Open Command Prompt / PowerShell in this folder.
3. Create a virtual environment (recommended):
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\activate
   ```
4. Install packages:
   ```powershell
   python -m pip install -r requirements.txt
   ```
5. Start the website:
   ```powershell
   python app.py
   ```
6. Open http://127.0.0.1:5000 in your browser.

The SQLite database `hostel_reports.db` is initialized automatically when you run `python app.py`.

## Demo accounts
- Student: username `student`, password `student123`
- Technician: username `technician`, password `tech12345`

You can also register a new account. This demo allows role selection during registration for coursework testing. In a real deployment, do not allow users to self-assign staff roles; create staff accounts through an administrator.

## Notes
- The optional attachment currently stores only the uploaded filename, not the file itself. Configure secure upload storage before using this beyond a local demo.
- The app limits form requests to 2 MB. Attachments are not persisted.
- Set a long, random `SECRET_KEY` environment variable for deployments. Without one, the app generates a temporary key when it starts, which invalidates existing sessions after a restart.
- Debug mode is disabled by default. Set `FLASK_DEBUG=1` only for local development.
- Add CSRF protection and rate limiting, assign staff roles administratively, and use HTTPS before deployment.
- This is a coursework starter project, not a production-ready security system.
