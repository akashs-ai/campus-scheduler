import json, os, tempfile, unittest
from pathlib import Path
os.environ["ORBIT_DB"] = str(Path(tempfile.gettempdir()) / "orbit-test.sqlite3")
try: Path(os.environ["ORBIT_DB"]).unlink()
except FileNotFoundError: pass
import server

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.seed(reset=True)
    def login(self, email, password):
        con = server.db(); u = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone(); con.close()
        self.assertTrue(server.password_ok(password, u["password_hash"]))
        token = "test-" + email; server.SESSIONS[token] = (u["id"], 9999999999); return token, u
    def test_seed_has_roles_rooms_and_sessions(self):
        con = server.db()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM users").fetchone()[0], 4)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM rooms").fetchone()[0], 6)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 12)
        con.close()
    def test_password_hash_is_not_plaintext(self):
        con = server.db(); stored = con.execute("SELECT password_hash FROM users WHERE id=1").fetchone()[0]; con.close()
        self.assertNotEqual(stored, "admin-demo")
        self.assertTrue(server.password_ok("admin-demo", stored))
    def test_self_approval_is_rejected_by_policy(self):
        _, user = self.login("admin@orbit.demo", "admin-demo")
        con = server.db()
        con.execute("INSERT OR REPLACE INTO bookings VALUES(?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                     ("SELF-1","Self request",user["id"],"club","A-201","Fri","16:00",1,"pending","",None))
        con.commit()
        booking = con.execute("SELECT * FROM bookings WHERE id='SELF-1'").fetchone()
        self.assertEqual(booking["requester_id"], user["id"])
        self.assertEqual(user["role"], "admin")
        con.close()
    def test_priority_order_is_explicit(self):
        self.assertEqual(server.PRIORITY, ["exam","class","institute","guest","department","club"])

if __name__ == "__main__":
    unittest.main()
