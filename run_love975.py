
import os
import sys
import time
import webbrowser
import threading

# Βρίσκει σωστά τον φάκελο είτε τρέχει ως .py είτε ως .exe
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)

from app import app, init_db

def open_browser():
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5000/admin")

if __name__ == "__main__":
    init_db()
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
