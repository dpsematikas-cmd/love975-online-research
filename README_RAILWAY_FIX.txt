RAILWAY FIX

Αν στο Railway εμφανιστεί "Application failed to respond", ανέβασε/αντικατάστησε αυτά τα αρχεία στο GitHub.

Περιλαμβάνει:
- Procfile
- railway.json
- gunicorn στο requirements.txt
- app.py που ακούει στο 0.0.0.0 και στο PORT του Railway

Μετά το GitHub update, το Railway θα κάνει redeploy μόνο του.
