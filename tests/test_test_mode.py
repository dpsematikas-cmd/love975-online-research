"""Run locally: python -m unittest discover -s tests -v
No production server, production database, or Railway access is required.
"""
import io
import os
import tempfile
import unittest

class TestModeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="love975-testmode-")
        os.environ["DATA_DIR"] = cls.tmp.name
        import app
        cls.app = app.app
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def admin_login(self):
        with self.client.session_transaction() as sess:
            sess["admin_logged_in"] = True

    def test_isolated_vote_and_export(self):
        from test_mode import connection, TEST_DB, TEST_UPLOADS
        from app import DB_PATH
        self.assertNotEqual(TEST_DB, DB_PATH)
        self.assertNotEqual(TEST_UPLOADS, os.path.join(os.environ["DATA_DIR"], "uploads"))
        self.admin_login()
        response = self.client.post("/test-mode/admin", data={
            "action":"upload",
            "songs":(io.BytesIO(b"ID3demo"),"Demo Artist - Demo Song.mp3"),
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        con = connection()
        song = con.execute("SELECT * FROM test_songs").fetchone()
        token = con.execute("SELECT value FROM test_settings WHERE key='invite'").fetchone()[0]
        self.assertIsNotNone(song)
        con.close()
        with self.client.session_transaction() as sess:
            sess.pop("admin_logged_in", None)
        self.assertEqual(self.client.get("/test-mode/").status_code,403)
        self.assertEqual(self.client.get("/test-mode/?invite="+token).status_code,200)
        data = {
            "name":"Test", "age":"35-44", "area":"Athens", "email":"test@example.com",
            "favorite_station":"LOVE RADIO 97.5", "listening_places":"Σπίτι",
            "listening_method":"Από internet", "listening_times":"Πρωί",
            f"song_{song['id']}":"LIKE",
        }
        self.assertEqual(self.client.post("/test-mode/submit",data=data).status_code,200)
        con=connection()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM test_participants").fetchone()[0],1)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM test_answers").fetchone()[0],1)
        con.close()
        self.assertEqual(self.client.post("/test-mode/submit",data=data).status_code,200)
        con=connection()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM test_participants").fetchone()[0],1)
        con.close()
        self.admin_login()
        excel=self.client.get("/test-mode/export-excel")
        self.assertEqual(excel.status_code,200)
        self.assertTrue(excel.data.startswith(b"PK"))
        self.assertEqual(self.client.post("/test-mode/admin",data={"action":"reset"}).status_code,200)
        con=connection()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM test_participants").fetchone()[0],0)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM test_songs").fetchone()[0],0)
        con.close()

if __name__=="__main__":
    unittest.main()
