
from flask import session, redirect, url_for, Flask, render_template, render_template_string, request, send_from_directory, send_file, redirect, url_for
from werkzeug.utils import secure_filename
import os, sqlite3, pandas as pd, json
from datetime import datetime
from io import BytesIO
from functools import wraps

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Μόνιμη αποθήκευση.
# Στο Railway θα βάλουμε Volume στο /app/data και DATA_DIR=/app/data
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(APP_DIR, "data"))
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "music_research.db")
ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a", "ogg", "aac"}

app = Flask(__name__)
app.secret_key = 'LOVE975_SECRET_KEY_2026'
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(DATA_DIR, exist_ok=True)
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
    cur.execute("""CREATE TABLE IF NOT EXISTS survey_archives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        closed_at TEXT,
        songs_count INTEGER,
        participants_count INTEGER,
        note TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS survey_archive_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        archive_id INTEGER,
        title TEXT,
        artist TEXT,
        n INTEGER,
        positive REAL,
        fav REAL,
        like_score REAL,
        soso REAL,
        burn REAL,
        negative REAL,
        unfamiliarity REAL,
        total_score REAL,
        age_json TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS song_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participant_id INTEGER,
        song_id INTEGER,
        answer_code TEXT,
        answered_at TEXT
    )""")
    archive_cols = [row[1] for row in cur.execute("PRAGMA table_info(survey_archives)").fetchall()]
    if "name" not in archive_cols:
        try:
            cur.execute("ALTER TABLE survey_archives ADD COLUMN name TEXT")
        except Exception:
            pass
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


def save_current_survey_archive(conn, archive_name=None):
    songs = conn.execute("SELECT * FROM songs ORDER BY id").fetchall()
    songs_count = len(songs)
    participants_count = conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0]
    closed_at = datetime.now().isoformat(timespec="seconds")

    if not archive_name:
        archive_name = "Έρευνα " + closed_at.replace("T", " ")

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO survey_archives (name, closed_at, songs_count, participants_count, note)
        VALUES (?, ?, ?, ?, ?)
    """, (
        archive_name,
        closed_at,
        songs_count,
        participants_count,
        "Archived survey: scores saved, audio files deleted"
    ))
    archive_id = cur.lastrowid

    summary_rows = build_summary(conn)
    for r in summary_rows:
        age_data = {}
        for age in AGE_GROUPS:
            age_data[age] = {
                "positive": r.get(f"POSITIVE {age}", 0),
                "total": r.get(f"TOTAL {age}", 0)
            }
        cur.execute("""
            INSERT INTO survey_archive_results
            (archive_id, title, artist, n, positive, fav, like_score, soso, burn, negative, unfamiliarity, total_score, age_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            archive_id,
            r.get("TITLE", ""),
            r.get("ARTIST", ""),
            int(r.get("N", 0) or 0),
            float(r.get("POSITIVE", 0) or 0),
            float(r.get("FAV", 0) or 0),
            float(r.get("LIKE", 0) or 0),
            float(r.get("SO&SO", 0) or 0),
            float(r.get("BURN", 0) or 0),
            float(r.get("NEGATIVE", 0) or 0),
            float(r.get("UNFAMILIARITY", 0) or 0),
            float(r.get("TOTAL_SCORE", 0) or 0),
            json.dumps(age_data, ensure_ascii=False)
        ))

    return archive_id

def get_archives(conn):
    return conn.execute("SELECT * FROM survey_archives ORDER BY id DESC").fetchall()



ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Dimitris1971#"

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin"))
        else:
            error = "Λάθος username ή password"

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="el">
    <head>
    <meta charset="UTF-8">
    <title>Love 97.5 Research Login</title>
    <style>
    body{
        background:#111;
        color:white;
        font-family:Arial;
        display:flex;
        align-items:center;
        justify-content:center;
        height:100vh;
    }
    .box{
        background:#1e1e1e;
        padding:40px;
        border-radius:18px;
        width:320px;
    }
    input{
        width:100%;
        padding:12px;
        margin-top:10px;
        border:none;
        border-radius:10px;
    }
    button{
        width:100%;
        padding:14px;
        margin-top:20px;
        border:none;
        border-radius:10px;
        background:#ffcc00;
        font-weight:bold;
    }
    h1{
        color:#ffcc00;
        text-align:center;
    }
    .err{
        color:#ff8080;
        margin-top:10px;
    }
    </style>
    </head>
    <body>
    <div class="box">
    <h1>Love 97.5<br>Online Research</h1>
    <form method="post">
    <input name="username" placeholder="Username">
    <input type="password" name="password" placeholder="Password">
    <button type="submit">LOGIN</button>
    </form>
    {% if error %}
    <div class="err">{{ error }}</div>
    {% endif %}
    </div>
    </body>
    </html>
    """, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
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

        elif action == "close_survey":
            archive_name = request.form.get("archive_name", "").strip()
            archive_id = save_current_survey_archive(conn, archive_name)

            songs = conn.execute("SELECT * FROM songs").fetchall()
            for song in songs:
                try:
                    os.remove(os.path.join(app.config["UPLOAD_FOLDER"], song["filename"]))
                except FileNotFoundError:
                    pass

            # Κρατάμε participants/song_answers για πλήρες raw export, αλλά μηδενίζουμε active songs.
            conn.execute("DELETE FROM songs")
            conn.commit()
            message = "Η έρευνα αρχειοθετήθηκε. Τα αποτελέσματα αποθηκεύτηκαν στο ιστορικό και τα mp3 διαγράφηκαν από τον server."
        elif action == "clear_results":
            conn.execute("DELETE FROM song_answers")
            conn.execute("DELETE FROM participants")
            conn.commit()
            message = "Καθαρίστηκαν τα αποτελέσματα."

    songs = conn.execute("SELECT * FROM songs ORDER BY id").fetchall()
    participants_count = conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0]
    summary = build_summary(conn)
    age_summary = build_age_group_summary(conn)
    archives = get_archives(conn)
    conn.close()

    return render_template(
        "admin.html",
        songs=songs,
        message=message,
        participants_count=participants_count,
        summary=summary,
        age_summary=age_summary,
        archives=archives,
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


@app.route("/export_archive_excel/<int:archive_id>")
def export_archive_excel(archive_id):
    conn = db()
    archive = conn.execute("SELECT * FROM survey_archives WHERE id=?", (archive_id,)).fetchone()
    if not archive:
        conn.close()
        return "Archive not found", 404

    rows = conn.execute("""
        SELECT title AS TITLE, artist AS ARTIST, n AS N, positive AS POSITIVE, fav AS FAV,
               like_score AS LIKE, soso AS "SO&SO", burn AS BURN, negative AS NEGATIVE,
               unfamiliarity AS UNFAMILIARITY, total_score AS TOTAL_SCORE, age_json
        FROM survey_archive_results
        WHERE archive_id=?
        ORDER BY total_score DESC
    """, (archive_id,)).fetchall()

    summary = []
    age_rows = []
    for row in rows:
        d = dict(row)
        age_json = d.pop("age_json", "{}")
        try:
            ages = json.loads(age_json)
        except Exception:
            ages = {}
        for age, vals in ages.items():
            d[f"POSITIVE {age}"] = vals.get("positive", 0)
            d[f"TOTAL {age}"] = vals.get("total", 0)
            age_rows.append({
                "TITLE": d["TITLE"],
                "ARTIST": d["ARTIST"],
                "AGE_GROUP": age,
                "POSITIVE": vals.get("positive", 0),
                "TOTAL_SCORE": vals.get("total", 0)
            })
        summary.append(d)

    summary_df = pd.DataFrame(summary)
    age_df = pd.DataFrame(age_rows)

    participants = conn.execute("SELECT * FROM participants ORDER BY id").fetchall()
    participants_df = pd.DataFrame([dict(r) for r in participants])
    conn.close()

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Archived Summary")
        age_df.to_excel(writer, index=False, sheet_name="Archived Age Groups")
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
    safe_name = (archive["name"] or f"archive_{archive_id}").replace(" ", "_").replace("/", "-")
    return send_file(
        output,
        as_attachment=True,
        download_name=f"love975_archive_{safe_name}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


# Railway startup init
try:
    init_db()
except Exception as e:
    print("DB init warning:", e)
