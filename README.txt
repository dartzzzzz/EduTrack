EDUTRACK | Local university resource portal
1. Extract the ZIP. Install Python 3.11 or newer if needed.
2. Double-click run.bat on Windows, or open a terminal in this folder and run:
   python -m pip install -r requirements.txt
   python app.py
3. Open http://127.0.0.1:5000 in your browser. Keep the terminal open.
4. Register a student account, sign in, upload a file.
5. Sign out and sign in as admin. The initial admin password is printed in the terminal on the first run. Save it securely. Optionally set EDUTRACK_ADMIN_PASSWORD before the first run.
6. Approve the upload in Admin review. Sign in as a student to rate and comment.
The database and uploads folder are created automatically. Each account can rate each resource once and update its rating. Popular means 10 or more page opens; repeat opens count. Guests can browse and download approved files. Login is required for uploads and feedback.
This is a local demonstration, not a production deployment. Before public use add institutional identity verification, HTTPS, malware scanning, moderation/reporting, rate limits, backups and a production server. Only upload material you have permission to share. JavaScript is used instead of Java. No sample files or personal data are included.
