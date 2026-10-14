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
   pip install -r requirements.txt
   ```
5. Start the website:
   ```powershell
   python app.py
   ```
6. Open http://127.0.0.1:5000 in your browser.

The SQLite database `hostel_reports.db` is created automatically on first run.

## Demo accounts
- Student: username `student`, password `student123`
- Technician: username `technician`, password `tech12345`

You can also register a new account. This demo allows role selection during registration for coursework testing. In a real deployment, do not allow users to self-assign staff roles; create staff accounts through an administrator.

## Notes
- The optional attachment currently stores only the uploaded filename, not the file itself. Configure secure upload storage before using this beyond a local demo.
- Change `SECRET_KEY` before deployment, turn off Flask debug mode in production, add CSRF protection and rate limiting, and use HTTPS.
- This is a coursework starter project, not a production-ready security system.
