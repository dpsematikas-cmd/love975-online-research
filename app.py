
from flask import Flask, render_template, request, send_from_directory, send_file, redirect, url_for
from werkzeug.utils import secure_filename
import os, sqlite3, pandas as pd
from datetime import datetime
from io import BytesIO

APP_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(APP_DIR, "uploads")
DB_PATH = os.path.join(APP_DIR, "music_research.db")
ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a", "ogg", "aac"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

RATING_OPTIONS = [
    ("UNFAM", "Δεν το έχετε ακουστά"),
    ("FAV", "Είναι από τα αγαπημένα σας"),
    ("LIKE", "Σας αρέσει απλά"),
    ("SOSO", "Ούτε σας αρέσει ούτε δε σας αρέσει"),
    ("BURN", "Σας άρεσε παλιότερα αλλά τώρα το έχετε βαρεθεί"),
    ("NEG", "Δεν σας αρέσει και ούτε ποτέ σας άρεσε"),
]

RADIO_STATIONS = [
    "ΣΚΑΙ 100.3", "SFERA 102.2", "bwin ΣΠΟΡ FM 94.6", "ΡΥΘΜΟΣ 94.9",
    "ΜΕΛΩΔΙΑ 99.2", "ΜΕΝΤΑ 88", "ΛΑΜΨΗ 92.3", "ΔΙΕΣΗ 101.3",
    "ΔΡΟΜΟΣ 89.8", "ATHENS DEE JAY 95.2", "HIT 88.9", "REAL FM 97.8",
    "96.9 ROCK FM", "RED 96.3", "PEPPER 96.6", "MUSIC 89.2",
    "EASY 97.2", "ΕΛΛΗΝΙΚΟΣ 93.2", "EN LEFKO 87.7", "HAPPY 104",
    "BEST 92.6", "REBEL 105.2", "GALAXY 92", "KISS FM 92.9",
    "LOVE RADIO 97.5", "KOSMOS 93.6", "MAD RADIO 106.2",
    "ΔΕΥΤΕΡΟ ΠΡΟΓΡΑΜΜΑ 103.7", "Άλλος σταθμός"
]

AGE_GROUPS = ["15-24", "25-34", "35-44", "45-54", "55-64", "65-74"]
LISTENING_PLACES = ["Σπίτι", "Αυτοκίνητο", "Δουλειά"]
LISTENING_METHODS = ["Από internet", "Από κανονικό ραδιόφωνο"]
LISTENING_TIMES = ["Πρωί", "Μεσημέρι", "Απόγευμα", "Βράδυ"]

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        artist TEXT,
        filename TEXT NOT NULL,
        original_filename TEXT,
        uploaded_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        age TEXT,
        area TEXT,
        email TEXT,
        marketing_consent TEXT,
        favorite_station TEXT,
        weekly_stations TEXT,
        listening_places TEXT,
        listening_method TEXT,
        listening_times TEXT,
        created_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS song_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participant_id INTEGER,
        song_id INTEGER,
        answer_code TEXT,
        answered_at TEXT
    )""")
    existing_cols = [row[1] for row in cur.execute("PRAGMA table_info(participants)").fetchall()]
    for col in ["listening_places", "listening_method", "listening_times"]:
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE participants ADD COLUMN {col} TEXT")
    conn.commit()
    conn.close()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_artist_title(filename):
    clean = os.path.splitext(filename)[0].strip()
    for sep in [" - ", " – ", " — ", "-", "–", "—"]:
        if sep in clean:
            parts = clean.split(sep, 1)
            artist = parts[0].strip()
            title = parts[1].strip()
            if artist and title:
                return artist, title
    return "", clean

def get_songs():
    conn = db()
    songs = conn.execute("SELECT * FROM songs ORDER BY id").fetchall()
    conn.close()
    return songs

@app.route("/")
def survey():
    songs = get_songs()
    if not songs:
        return render_template("no_songs.html")
    return render_template(
        "survey.html",
        songs=songs,
        rating_options=RATING_OPTIONS,
        radio_stations=RADIO_STATIONS,
        age_groups=AGE_GROUPS,
        listening_places=LISTENING_PLACES,
        listening_methods=LISTENING_METHODS,
        listening_times=LISTENING_TIMES
    )

@app.route("/submit", methods=["POST"])
def submit():
    songs = get_songs()
    name = request.form.get("name", "").strip()
    age = request.form.get("age", "").strip()
    area = request.form.get("area", "").strip()
    email = request.form.get("email", "").strip()
    marketing_consent = "YES" if request.form.get("marketing_consent") == "on" else "NO"
    favorite_station = request.form.get("favorite_station", "").strip()
    weekly_stations = request.form.getlist("weekly_stations")
    listening_places = request.form.getlist("listening_places")
    listening_method = request.form.get("listening_method", "").strip()
    listening_times = request.form.getlist("listening_times")

    if not age or not area or not email or not favorite_station or not listening_places or not listening_method or not listening_times:
        return "Λείπουν υποχρεωτικά πεδία.", 400

    if favorite_station in weekly_stations:
        return "Το αγαπημένο ραδιόφωνο δεν μπορεί να επιλεγεί και στη δεύτερη ερώτηση.", 400

    for song in songs:
        if not request.form.get(f"song_{song['id']}"):
            return "Πρέπει να απαντήσεις σε κάθε τραγούδι.", 400

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO participants
        (name, age, area, email, marketing_consent, favorite_station, weekly_stations, listening_places, listening_method, listening_times, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name, age, area, email, marketing_consent, favorite_station,
        " | ".join(weekly_stations),
        " | ".join(listening_places),
        listening_method,
        " | ".join(listening_times),
        datetime.now().isoformat(timespec="seconds")
    ))
    participant_id = cur.lastrowid

    for song in songs:
        answer_code = request.form.get(f"song_{song['id']}")
        cur.execute("""
            INSERT INTO song_answers (participant_id, song_id, answer_code, answered_at)
            VALUES (?, ?, ?, ?)
        """, (participant_id, song["id"], answer_code, datetime.now().isoformat(timespec="seconds")))

    conn.commit()
    conn.close()
    return render_template("thanks.html")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    init_db()
    conn = db()
    message = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "upload_songs":
            files = request.files.getlist("songs")
            existing_count = conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
            slots = max(0, 30 - existing_count)
            added = 0

            for file in files[:slots]:
                if file and allowed_file(file.filename):
                    original_name = file.filename
                    artist, title = parse_artist_title(original_name)
                    safe = secure_filename(original_name)
                    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                    filename = f"{stamp}_{safe}"
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                    conn.execute("""
                        INSERT INTO songs (title, artist, filename, original_filename, uploaded_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (title, artist, filename, original_name, datetime.now().isoformat(timespec="seconds")))
                    added += 1

            conn.commit()
            if added == 0:
                message = "Δεν προστέθηκε τραγούδι. Έλεγξε ότι είναι mp3, wav, m4a, ogg ή aac."
            else:
                message = f"Προστέθηκαν {added} τραγούδια. Σύνολο έως 30."

        elif action == "delete_song":
            song_id = request.form.get("song_id")
            song = conn.execute("SELECT * FROM songs WHERE id=?", (song_id,)).fetchone()
            if song:
                try:
                    os.remove(os.path.join(app.config["UPLOAD_FOLDER"], song["filename"]))
                except FileNotFoundError:
                    pass
                conn.execute("DELETE FROM song_answers WHERE song_id=?", (song_id,))
                conn.execute("DELETE FROM songs WHERE id=?", (song_id,))
                conn.commit()
                message = "Το τραγούδι διαγράφηκε."

        elif action == "clear_songs":
            songs = conn.execute("SELECT * FROM songs").fetchall()
            for song in songs:
                try:
                    os.remove(os.path.join(app.config["UPLOAD_FOLDER"], song["filename"]))
                except FileNotFoundError:
                    pass
            conn.execute("DELETE FROM song_answers")
            conn.execute("DELETE FROM songs")
            conn.commit()
            message = "Καθαρίστηκαν όλα τα τραγούδια."

        elif action == "clear_results":
            conn.execute("DELETE FROM song_answers")
            conn.execute("DELETE FROM participants")
            conn.commit()
            message = "Καθαρίστηκαν τα αποτελέσματα."

    songs = conn.execute("SELECT * FROM songs ORDER BY id").fetchall()
    participants_count = conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0]
    summary = build_summary(conn)
    age_summary = build_age_group_summary(conn)
    conn.close()

    return render_template(
        "admin.html",
        songs=songs,
        message=message,
        participants_count=participants_count,
        summary=summary,
        age_summary=age_summary,
        max_songs=30
    )

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

def pct(n, total):
    if total == 0:
        return 0
    return round((n / total) * 100, 2)


def counts_for_rows(rows):
    counts = {code: 0 for code, _ in RATING_OPTIONS}
    for r in rows:
        if r["answer_code"] in counts:
            counts[r["answer_code"]] += 1
    return counts

def metrics_from_counts(counts, total):
    fav = pct(counts["FAV"], total)
    like = pct(counts["LIKE"], total)
    positive = round(fav + like, 2)
    neg = pct(counts["NEG"], total)
    unfam = pct(counts["UNFAM"], total)
    burn = pct(counts["BURN"], total)
    soso = pct(counts["SOSO"], total)
    total_score = round(max(0, positive - (neg * 0.7) - (burn * 0.35) - (unfam * 0.2)), 2)
    return {
        "N": total,
        "POSITIVE": positive,
        "FAV": fav,
        "LIKE": like,
        "SO&SO": soso,
        "BURN": burn,
        "NEGATIVE": neg,
        "UNFAMILIARITY": unfam,
        "TOTAL_SCORE": total_score
    }

def build_summary(conn):
    songs = conn.execute("SELECT * FROM songs ORDER BY id").fetchall()
    rows = []

    for song in songs:
        answers = conn.execute("SELECT answer_code FROM song_answers WHERE song_id=?", (song["id"],)).fetchall()
        counts = counts_for_rows(answers)
        row = {
            "TITLE": song["title"],
            "ARTIST": song["artist"],
            **metrics_from_counts(counts, len(answers))
        }

        # Στήλες ανά ηλικιακό group στο βασικό Radio Summary
        for age in AGE_GROUPS:
            age_rows = conn.execute("""
                SELECT sa.answer_code FROM song_answers sa
                JOIN participants p ON p.id = sa.participant_id
                WHERE sa.song_id=? AND p.age=?
            """, (song["id"], age)).fetchall()
            age_counts = counts_for_rows(age_rows)
            age_metrics = metrics_from_counts(age_counts, len(age_rows))
            row[f"POSITIVE {age}"] = age_metrics["POSITIVE"]
            row[f"TOTAL {age}"] = age_metrics["TOTAL_SCORE"]

        rows.append(row)

    rows.sort(key=lambda x: x["TOTAL_SCORE"], reverse=True)
    return rows

def build_age_group_summary(conn):
    songs = conn.execute("SELECT * FROM songs ORDER BY id").fetchall()
    rows = []
    for song in songs:
        for age in AGE_GROUPS:
            age_rows = conn.execute("""
                SELECT sa.answer_code FROM song_answers sa
                JOIN participants p ON p.id = sa.participant_id
                WHERE sa.song_id=? AND p.age=?
            """, (song["id"], age)).fetchall()
            age_counts = counts_for_rows(age_rows)
            rows.append({
                "TITLE": song["title"],
                "ARTIST": song["artist"],
                "AGE_GROUP": age,
                **metrics_from_counts(age_counts, len(age_rows))
            })
    rows.sort(key=lambda x: (x["TITLE"], x["AGE_GROUP"]))
    return rows


@app.route("/export_excel")
def export_excel():
    conn = db()
    summary_df = pd.DataFrame(build_summary(conn))
    age_summary_df = pd.DataFrame(build_age_group_summary(conn))

    raw = conn.execute("""
        SELECT
            p.id AS participant_id,
            p.name,
            p.age,
            p.area,
            p.email,
            p.marketing_consent,
            p.favorite_station,
            p.weekly_stations,
            p.listening_places,
            p.listening_method,
            p.listening_times,
            s.artist,
            s.title,
            sa.answer_code,
            CASE sa.answer_code
                WHEN 'UNFAM' THEN 'Δεν το έχετε ακουστά'
                WHEN 'FAV' THEN 'Είναι από τα αγαπημένα σας'
                WHEN 'LIKE' THEN 'Σας αρέσει απλά'
                WHEN 'SOSO' THEN 'Ούτε σας αρέσει ούτε δε σας αρέσει'
                WHEN 'BURN' THEN 'Σας άρεσε παλιότερα αλλά τώρα το έχετε βαρεθεί'
                WHEN 'NEG' THEN 'Δεν σας αρέσει και ούτε ποτέ σας άρεσε'
            END AS answer_text,
            sa.answered_at
        FROM song_answers sa
        JOIN participants p ON p.id = sa.participant_id
        JOIN songs s ON s.id = sa.song_id
        ORDER BY p.id, s.id
    """).fetchall()
    raw_df = pd.DataFrame([dict(r) for r in raw])

    participants = conn.execute("SELECT * FROM participants ORDER BY id").fetchall()
    participants_df = pd.DataFrame([dict(r) for r in participants])
    conn.close()

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Radio Summary")
        age_summary_df.to_excel(writer, index=False, sheet_name="Age Group Summary")
        raw_df.to_excel(writer, index=False, sheet_name="Raw Song Answers")
        participants_df.to_excel(writer, index=False, sheet_name="Participants")

        wb = writer.book
        for ws in wb.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                max_len = 10
                letter = col[0].column_letter
                for cell in col:
                    value = str(cell.value) if cell.value is not None else ""
                    max_len = max(max_len, min(len(value), 45))
                ws.column_dimensions[letter].width = max_len + 2

    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="love975_music_research_results.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
