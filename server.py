"""Small production-shaped API for Orbit using only Python's standard library.

The UI remains deployable as static assets, while this service supplies secure
server-side authorization, SQLite persistence, deterministic booking decisions,
audit events, and export generation.
"""
from __future__ import annotations
import hashlib, hmac, json, os, secrets, sqlite3, time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
DB_PATH = Path(os.environ.get("ORBIT_DB", ROOT / "orbit.sqlite3"))
SESSION_TTL = 8 * 60 * 60
PRIORITY = ["exam", "class", "institute", "guest", "department", "club"]
ROLE_PERMISSIONS = {
    "admin": {"approve", "generate", "reset", "manage"},
    "coordinator": {"request", "department_approve"},
    "faculty": {"request"},
    "club": {"request", "cancel_own"},
}
SESSIONS: dict[str, tuple[int, float]] = {}

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + "$" + digest.hex()

def password_ok(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=16384, r=8, p=1)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False

def audit(con, actor, action, entity_type, entity_id, details):
    con.execute("INSERT INTO audit_events(actor_id,action,entity_type,entity_id,details_json) VALUES(?,?,?,?,?)",
                (actor, action, entity_type, entity_id, json.dumps(details, separators=(",", ":"))))

def seed(reset=False):
    con = db()
    con.executescript((ROOT / "schema.sql").read_text())
    if reset or con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        con.execute("DELETE FROM audit_events"); con.execute("DELETE FROM bookings")
        con.execute("DELETE FROM sessions"); con.execute("DELETE FROM rooms"); con.execute("DELETE FROM users")
        users = [
            (1, "admin@orbit.demo", "Dean's Office", "admin", None, "admin-demo"),
            (2, "coordinator@orbit.demo", "BCA Coordinator", "coordinator", "BCA", "coordinator-demo"),
            (3, "faculty@orbit.demo", "Dr. Mehta", "faculty", "BCA", "faculty-demo"),
            (4, "club@orbit.demo", "Robotics Club", "club", None, "club-demo"),
        ]
        con.executemany("INSERT INTO users VALUES(?,?,?,?,?,?,1)", [(i,e,n,r,d,password_hash(p)) for i,e,n,r,d,p in users])
        rooms = [
            ("A-201",72,"Lecture hall",1,["Projector","AC"],[]),("A-105",48,"Classroom",1,["Projector","Whiteboard"],[]),
            ("Lab E-1",36,"Computer lab",0,["32 PCs","AC"],[{"day":"Fri","start":"09:00","end":"18:00"}]),
            ("Lab E-2",40,"Electronics lab",1,["Oscilloscope","AC"],[]),("B-104",64,"Classroom",1,["Projector"],[]),
            ("Auditorium",450,"Auditorium",1,["Stage","AV","Green room"],[])
        ]
        con.executemany("INSERT INTO rooms(name,capacity,room_type,accessible,features_json,maintenance_json) VALUES(?,?,?,?,?,?)",
                        [(n,c,t,a,json.dumps(f),json.dumps(m)) for n,c,t,a,f,m in rooms])
        sessions = json.loads((ROOT / "exports" / "schedule.json").read_text())["sessions"]
        details = {
            "CS201":"Data Structures","MA102":"Discrete Mathematics","EC210":"Digital Systems","CS305":"Operating Systems",
            "HU110":"Professional Communication","EC302":"Microprocessors","CS220":"Database Systems","MA205":"Probability & Statistics",
            "EC202":"Signals & Systems","CS401":"Cloud Computing","EC415":"Embedded Systems Lab","HU205":"Ethics & Society"
        }
        con.executemany("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?)", [
            (s["sessionId"],s["courseCode"],details.get(s["courseCode"],s["courseCode"]), "Assigned faculty",
             "Assigned group",s["day"],s["startPeriod"],s["room"]) for s in sessions])
        con.executemany("INSERT INTO settings(key,value_json) VALUES(?,?)",
                        [("booking_priority", json.dumps(PRIORITY)), ("schedule_revision", json.dumps({"id":"REV-001","moved":0}))])
        audit(con, 1, "demo_seeded", "system", "seed", {"reset": reset})
        con.commit()
    con.close()

def json_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length > 1_000_000: raise ValueError("payload too large")
    return json.loads(handler.rfile.read(length) or b"{}")

def response(handler, status, value):
    raw = json.dumps(value, separators=(",", ":")).encode()
    handler.send_response(status); handler.send_header("Content-Type","application/json")
    handler.send_header("Content-Length", str(len(raw))); handler.send_header("Cache-Control","no-store"); handler.end_headers()
    handler.wfile.write(raw)

def auth(handler):
    token = handler.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    record = SESSIONS.get(token)
    if not record or record[1] < time.time():
        if token: SESSIONS.pop(token, None)
        return None
    con = db(); user = con.execute("SELECT * FROM users WHERE id=? AND active=1", (record[0],)).fetchone(); con.close()
    return user

def room_conflict(con, room, day, start, duration):
    return con.execute("""SELECT 1 FROM bookings WHERE room=? AND day=? AND start_period=? AND status IN ('pending','approved') LIMIT 1""",
                       (room, day, start)).fetchone() is not None

class API(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health": return response(self, 200, {"ok": True, "database": str(DB_PATH.name)})
        user = auth(self)
        if not user: return response(self, 401, {"error":"authentication_required"})
        con = db()
        try:
            if path == "/api/me": return response(self, 200, {"id":user["id"],"email":user["email"],"name":user["display_name"],"role":user["role"],"department":user["department"]})
            if path == "/api/rooms":
                rows = con.execute("SELECT * FROM rooms ORDER BY name").fetchall()
                return response(self, 200, [{"name":r["name"],"capacity":r["capacity"],"type":r["room_type"],"accessible":bool(r["accessible"]),"features":json.loads(r["features_json"]),"maintenance":json.loads(r["maintenance_json"])} for r in rows])
            if path == "/api/timetable":
                return response(self, 200, [dict(r) for r in con.execute("SELECT * FROM sessions ORDER BY day,start_period").fetchall()])
            if path == "/api/bookings":
                return response(self, 200, [dict(r) for r in con.execute("""SELECT b.*,u.display_name requester FROM bookings b JOIN users u ON u.id=b.requester_id ORDER BY b.created_at DESC""").fetchall()])
            if path == "/api/audit" and user["role"] == "admin":
                return response(self, 200, [dict(r) for r in con.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 100").fetchall()])
            return response(self, 404, {"error":"not_found"})
        finally: con.close()

    def do_POST(self):
        path = urlparse(self.path).path
        try: body = json_body(self)
        except (ValueError, json.JSONDecodeError): return response(self, 400, {"error":"invalid_json"})
        if path == "/api/auth/login":
            con = db(); user = con.execute("SELECT * FROM users WHERE email=? AND active=1", (str(body.get("email","")).lower().strip(),)).fetchone(); con.close()
            if not user or not password_ok(str(body.get("password","")), user["password_hash"]):
                return response(self, 401, {"error":"invalid_credentials"})
            token = secrets.token_urlsafe(32); SESSIONS[token] = (user["id"], time.time() + SESSION_TTL)
            return response(self, 200, {"token":token,"expiresIn":SESSION_TTL,"user":{"id":user["id"],"name":user["display_name"],"role":user["role"]}})
        user = auth(self)
        if not user: return response(self, 401, {"error":"authentication_required"})
        con = db()
        try:
            if path == "/api/bookings":
                required = ["title","kind","room","day","start_period"]
                if any(not body.get(x) for x in required): return response(self, 422, {"error":"title, kind, room, day and start_period are required"})
                room = con.execute("SELECT * FROM rooms WHERE name=?", (body["room"],)).fetchone()
                if not room: return response(self, 422, {"error":"room_not_found"})
                if room_conflict(con, body["room"], body["day"], body["start_period"], int(body.get("duration",1))):
                    reason = "Room/time is already reserved by a higher or equal priority request."
                    status = "rejected"
                else:
                    reason = "Request received; deterministic conflict and priority checks passed."
                    status = "pending"
                bid = "BK-" + secrets.token_hex(4).upper()
                con.execute("INSERT INTO bookings(id,title,requester_id,kind,room,day,start_period,duration,status,decision_reason) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (bid,body["title"],user["id"],body["kind"],body["room"],body["day"],body["start_period"],int(body.get("duration",1)),status,reason))
                audit(con,user["id"],"booking_created","booking",bid,{"status":status,"kind":body["kind"]}); con.commit()
                return response(self, 201, {"id":bid,"status":status,"reason":reason})
            if path.startswith("/api/bookings/") and path.endswith("/decision"):
                if user["role"] != "admin": return response(self, 403, {"error":"admin_approval_required"})
                bid = path.split("/")[3]; booking = con.execute("SELECT * FROM bookings WHERE id=?", (bid,)).fetchone()
                if not booking: return response(self, 404, {"error":"booking_not_found"})
                if booking["requester_id"] == user["id"]: return response(self, 403, {"error":"cannot_approve_own_request"})
                decision = body.get("decision")
                if decision not in ("approved","rejected"): return response(self, 422, {"error":"decision_must_be_approved_or_rejected"})
                con.execute("UPDATE bookings SET status=?,decision_reason=?,decided_by=? WHERE id=?", (decision, body.get("reason","Admin decision recorded."),user["id"],bid))
                audit(con,user["id"],"booking_decided","booking",bid,{"decision":decision}); con.commit()
                return response(self, 200, {"id":bid,"status":decision})
            if path == "/api/admin/reset":
                if user["role"] != "admin": return response(self, 403, {"error":"admin_required"})
                seed(reset=True); return response(self, 200, {"ok":True})
            return response(self, 404, {"error":"not_found"})
        finally: con.close()

def main():
    seed()
    port = int(os.environ.get("PORT", "8080"))
    print(f"Orbit API listening on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), API).serve_forever()

if __name__ == "__main__":
    main()
