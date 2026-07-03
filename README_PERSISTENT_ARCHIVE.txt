PERSISTENT STORAGE + ARCHIVES

ΝΕΟ:
- Η βάση και τα uploads αποθηκεύονται στο DATA_DIR.
- Στο Railway βάλε Volume mount path: /app/data
- Βάλε Variable: DATA_DIR=/app/data
- Μην ανεβάζεις ποτέ ξανά music_research.db στο GitHub.

Στο admin:
- Κλείσιμο έρευνας & διαγραφή mp3
- Αποθηκεύει summary στο ιστορικό παλιών ερευνών.
- Σβήνει mp3 ώστε να μη γεμίζει ο server.
- Μπορείς να κάνεις export παλιές έρευνες από το Ιστορικό.
