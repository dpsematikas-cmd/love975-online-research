"""Isolated TEST MODE for LOVE music research.

This blueprint deliberately never opens the live music_research.db or live uploads.
It is only registered on the feature branch until an explicit production approval.
"""
import os
import sqlite3
from datetime import datetime
from io import BytesIO
import pandas as pd
from flask import Blueprint, request, render_template, redirect, url_for, session, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename

test_bp = Blueprint("test_mode", __name__, url_prefix="/test-mode")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
TEST_DB = os.path.join(DATA_DIR, "test_mode_research.db")
TEST_UPLOADS = os.path.join(DATA_DIR, "test_mode_uploads")
ALLOWED = {"mp3", "wav", "m4a", "ogg", "aac"}
CODES = {"UNFAM", "FAV", "LIKE", "SOSO", "BURN", "NEG"}

def connection():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(TEST_UPLOADS, exist_ok=True)
    con = sqlite3.connect(TEST_DB)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS test_songs (
        id INTEGER PRIMARY KEY, title TEXT NOT NULL, artist TEXT, filename TEXT NOT NULL,
        original_filename TEXT, created_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS test_participants (
        id INTEGER PRIMARY KEY, name TEXT, age TEXT, area TEXT, email TEXT,
        email_normalized TEXT UNIQUE, marketing_consent TEXT, favorite_station TEXT,
        weekly_stations TEXT, listening_places TEXT, listening_method TEXT,
        listening_times TEXT, created_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS test_answers (
        participant_id INTEGER, song_id INTEGER, answer_code TEXT, answered_at TEXT,
        PRIMARY KEY (participant_id, song_id))""")
    con.commit()
    return con

def admin_only():
    return session.get("admin_logged_in") is True

def normalize(email):
    return (email or "").strip().lower()

def songs_for(con):
    return con.execute("SELECT * FROM test_songs ORDER BY id").fetchall()

@test_bp.route("/admin", methods=["GET", "POST"])
def admin():
    if not admin_only():
        return redirect(url_for("admin_login"))
    con = connection()
    msg = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "upload":
            count = con.execute("SELECT COUNT(*) FROM test_songs").fetchone()[0]
            added = 0
            for f in request.files.getlist("songs"):
                if count + added >= 30:
                    break
                if not f or "." not in f.filename or f.filename.rsplit(".",1)[1].lower() not in ALLOWED:
                    continue
                original = f.filename
                if con.execute("SELECT 1 FROM test_songs WHERE original_filename=?", (original,)).fetchone():
                    continue
                stem = os.path.splitext(original)[0]
                parts = stem.split(" - ", 1)
                artist, title = (parts[0], parts[1]) if len(parts) == 2 else ("", stem)
                filename = datetime.now().strftime("%Y%m%d%H%M%S%f") + "_" + secure_filename(original)
                f.save(os.path.join(TEST_UPLOADS, filename))
                con.execute("INSERT INTO test_songs (title,artist,filename,original_filename,created_at) VALUES (?,?,?,?,?)",
                            (title,artist,filename,original,datetime.now().isoformat()))
                added += 1
            con.commit()
            msg = f"Προστέθηκαν {added} δοκιμαστικά τραγούδια."
        elif action == "reset":
            # Clear only TEST data and TEST audio; live DB and audio are never touched.
            filenames = [x["filename"] for x in songs_for(con)]
            con.execute("DELETE FROM test_answers")
            con.execute("DELETE FROM test_participants")
            con.execute("DELETE FROM test_songs")
            con.commit()
            for name in filenames:
                try: os.remove(os.path.join(TEST_UPLOADS, name))
                except FileNotFoundError: pass
            msg = "Μηδενίστηκε μόνο η δοκιμαστική έρευνα."
        elif action == "delete_song":
            song = con.execute("SELECT * FROM test_songs WHERE id=?", (request.form.get("song_id"),)).fetchone()
            if song:
                con.execute("DELETE FROM test_answers WHERE song_id=?", (song["id"],))
                con.execute("DELETE FROM test_songs WHERE id=?", (song["id"],))
                con.commit()
                try: os.remove(os.path.join(TEST_UPLOADS, song["filename"]))
                except FileNotFoundError: pass
                msg = "Το δοκιμαστικό τραγούδι διαγράφηκε."
    songs = songs_for(con)
    participants = con.execute("SELECT COUNT(*) FROM test_participants").fetchone()[0]
    summary = summary_for(con)
    con.close()
    return render_template("test_admin.html", songs=songs, participants_count=participants,
                           summary=summary, message=msg)

@test_bp.route("/")
def survey():
    con = connection()
    songs = songs_for(con)
    con.close()
    if not songs:
        return render_template("no_songs.html")
    # Reuse the exact same listener form and six rating options as the live app.
    from app import RATING_OPTIONS, RADIO_STATIONS, AGE_GROUPS, LISTENING_PLACES, LISTENING_METHODS, LISTENING_TIMES
    return render_template("survey.html", songs=songs, rating_options=RATING_OPTIONS,
                           radio_stations=RADIO_STATIONS, age_groups=AGE_GROUPS,
                           listening_places=LISTENING_PLACES, listening_methods=LISTENING_METHODS,
                           listening_times=LISTENING_TIMES, check_endpoint="test_mode.check_email",
                           submit_endpoint="test_mode.submit", audio_endpoint="test_mode.audio")

@test_bp.route("/audio/<path:filename>")
def audio(filename):
    con = connection()
    exists = con.execute("SELECT 1 FROM test_songs WHERE filename=?", (filename,)).fetchone()
    con.close()
    if not exists:
        return "Not found", 404
    return send_from_directory(TEST_UPLOADS, filename)

def fields():
    f = request.form
    return dict(name=f.get("name","").strip(), age=f.get("age","").strip(),
                area=f.get("area","").strip(), email=f.get("email","").strip(),
                email_normalized=normalize(f.get("email")),
                marketing_consent="YES" if f.get("marketing_consent") == "on" else "NO",
                favorite_station=f.get("favorite_station","").strip(),
                weekly_stations=f.getlist("weekly_stations"), listening_places=f.getlist("listening_places"),
                listening_method=f.get("listening_method","").strip(), listening_times=f.getlist("listening_times"))

def validate(d):
    if not all([d["age"], d["area"], d["email"], d["favorite_station"], d["listening_places"], d["listening_method"], d["listening_times"]]):
        return "Λείπουν υποχρεωτικά πεδία."
    if d["favorite_station"] in d["weekly_stations"]:
        return "Το αγαπημένο ραδιόφωνο δεν μπορεί να επιλεγεί και στη δεύτερη ερώτηση."
    return None

@test_bp.route("/check-email", methods=["POST"])
def check_email():
    d = fields()
    err = validate(d)
    if err: return jsonify(ok=False, error=err), 400
    con = connection()
    voted = con.execute("SELECT 1 FROM test_participants WHERE email_normalized=?", (d["email_normalized"],)).fetchone()
    con.close()
    if voted: return render_template("already_voted.html", email=d["email"])
    return jsonify(ok=True)

@test_bp.route("/submit", methods=["POST"])
def submit():
    d = fields()
    err = validate(d)
    if err: return err, 400
    con = connection()
    songs = songs_for(con)
    if not songs:
        con.close()
        return "Δεν υπάρχουν δοκιμαστικά τραγούδια.", 400
    if any(request.form.get(f"song_{s['id']}") not in CODES for s in songs):
        con.close()
        return "Απαιτείται έγκυρη απάντηση σε κάθε τραγούδι.", 400
    now = datetime.now().isoformat(timespec="seconds")
    try:
        cur = con.execute("""INSERT INTO test_participants
            (name,age,area,email,email_normalized,marketing_consent,favorite_station,
             weekly_stations,listening_places,listening_method,listening_times,created_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
             (d["name"],d["age"],d["area"],d["email"],d["email_normalized"],
              d["marketing_consent"],d["favorite_station"]," | ".join(d["weekly_stations"]),
              " | ".join(d["listening_places"]),d["listening_method"]," | ".join(d["listening_times"]),now))
        for song in songs:
            con.execute("INSERT INTO test_answers VALUES (?,?,?,?)",
                        (cur.lastrowid, song["id"], request.form[f"song_{song['id']}"], now))
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback()
        con.close()
        return render_template("already_voted.html", email=d["email"])
    finally:
        try: con.close()
        except Exception: pass
    return render_template("thanks.html")

def summary_for(con):
    from app import counts_for_rows, metrics_from_counts, AGE_GROUPS
    result = []
    for song in songs_for(con):
        rows = con.execute("SELECT answer_code FROM test_answers WHERE song_id=?", (song["id"],)).fetchall()
        item = {"TITLE":song["title"], "ARTIST":song["artist"],
                **metrics_from_counts(counts_for_rows(rows), len(rows))}
        for age in AGE_GROUPS:
            age_rows = con.execute("""SELECT a.answer_code FROM test_answers a
                JOIN test_participants p ON p.id=a.participant_id
                WHERE a.song_id=? AND p.age=?""", (song["id"],age)).fetchall()
            metrics = metrics_from_counts(counts_for_rows(age_rows),len(age_rows))
            item[f"POSITIVE {age}"] = metrics["POSITIVE"]
            item[f"TOTAL {age}"] = metrics["TOTAL_SCORE"]
        result.append(item)
    return sorted(result,key=lambda x:x["TOTAL_SCORE"],reverse=True)

@test_bp.route("/export-excel")
def export_excel():
    if not admin_only(): return redirect(url_for("admin_login"))
    from app import AGE_GROUPS, counts_for_rows, metrics_from_counts
    con = connection()
    summary = summary_for(con)
    ages = []
    for song in songs_for(con):
        for age in AGE_GROUPS:
            rows = con.execute("""SELECT a.answer_code FROM test_answers a
                JOIN test_participants p ON p.id=a.participant_id
                WHERE a.song_id=? AND p.age=?""",(song["id"],age)).fetchall()
            ages.append({"TITLE":song["title"],"ARTIST":song["artist"],"AGE_GROUP":age,
                         **metrics_from_counts(counts_for_rows(rows),len(rows))})
    raw = con.execute("""SELECT p.id AS participant_id,p.name,p.age,p.area,p.email,p.marketing_consent,
       p.favorite_station,p.weekly_stations,p.listening_places,p.listening_method,p.listening_times,
       s.artist,s.title,a.answer_code,a.answered_at
       FROM test_answers a JOIN test_participants p ON p.id=a.participant_id
       JOIN test_songs s ON s.id=a.song_id ORDER BY p.id,s.id""").fetchall()
    participants = con.execute("SELECT * FROM test_participants ORDER BY id").fetchall()
    con.close()
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        pd.DataFrame(summary).to_excel(writer,index=False,sheet_name="Radio Summary")
        pd.DataFrame(ages).to_excel(writer,index=False,sheet_name="Age Group Summary")
        pd.DataFrame([dict(x) for x in raw]).to_excel(writer,index=False,sheet_name="Raw Song Answers")
        pd.DataFrame([dict(x) for x in participants]).to_excel(writer,index=False,sheet_name="Participants")
        for ws in writer.book.worksheets:
            ws.freeze_panes="A2"
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width=min(48,max(12,max(len(str(c.value or "")) for c in col)+2))
    out.seek(0)
    return send_file(out,as_attachment=True,download_name="love975_TEST_results.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
