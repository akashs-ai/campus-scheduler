"""Orbit API: secure demo-ready persistence and authorization service."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
DB_PATH = Path(os.environ.get("ORBIT_DB", ROOT / "orbit.sqlite3"))
ENV = os.environ.get("ORBIT_ENV", "development").lower()
SESSION_TTL = 8 * 60 * 60
MAX_LOGIN_ATTEMPTS = 8
PRIORITY = ["exam", "class", "institute", "guest", "department", "club"]
KINDS = set(PRIORITY)
DAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
TIMES = {"09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00", "18:00"}
EMAIL_RE = re.compile(r"^[^@\s]{1,80}@[^@\s]{1,120}\.[^@\s]{2,30}$")


def db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 5000")
    return con


def password_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + "$" + digest.hex()


def password_ok(password, stored):
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=16384, r=8, p=1)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def audit(con, actor, action, entity_type, entity_id, details):
    con.execute(
        "INSERT INTO audit_events(actor_id,action,entity_type,entity_id,details_json) VALUES(?,?,?,?,?)",
        (actor, action, entity_type, entity_id, json.dumps(details, separators=(",", ":"))),
    )


def seed(reset=False):
    con = db()
    con.executescript((ROOT / "schema.sql").read_text())
    columns = {row["name"] for row in con.execute("PRAGMA table_info(users)").fetchall()}
    if "status" not in columns:
        con.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
    if "approved_by" not in columns:
        con.execute("ALTER TABLE users ADD COLUMN approved_by INTEGER")
    if "created_at" not in columns:
        con.execute("ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")
    count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if not reset and count:
        con.close()
        return
    if ENV == "production" and (reset or count == 0):
        con.close()
        raise RuntimeError("Production requires an explicit external bootstrap; demo seeding is disabled.")
    if reset:
        for table in ("auth_sessions", "auth_attempts", "audit_events", "bookings", "sessions", "rooms", "users"):
            con.execute(f"DELETE FROM {table}")
    users = [
        (1, "admin@orbit.demo", "Dean's Office", "admin", None, "admin-demo", "active", 1),
        (2, "coordinator@orbit.demo", "BCA Coordinator", "coordinator", "BCA", "coordinator-demo", "active", 1),
        (3, "faculty@orbit.demo", "Dr. Mehta", "faculty", "BCA", "faculty-demo", "active", 1),
        (4, "club@orbit.demo", "Robotics Club", "club", None, "club-demo", "active", 1),
    ]
    if count == 0 or reset:
        con.executemany(
            "INSERT INTO users(id,email,display_name,role,department,password_hash,status,active) VALUES(?,?,?,?,?,?,?,?)",
            [(i, e, n, r, d, password_hash(p), s, a) for i, e, n, r, d, p, s, a in users],
        )
        rooms = [
            ("A-201", 72, "Lecture hall", 1, ["Projector", "AC"], []),
            ("A-105", 48, "Classroom", 1, ["Projector", "Whiteboard"], []),
            ("Lab E-1", 36, "Computer lab", 0, ["32 PCs", "AC"], [{"day": "Fri", "start": "09:00", "end": "18:00"}]),
            ("Lab E-2", 40, "Electronics lab", 1, ["Oscilloscope", "AC"], []),
            ("B-104", 64, "Classroom", 1, ["Projector"], []),
            ("Auditorium", 450, "Auditorium", 1, ["Stage", "AV", "Green room"], []),
        ]
        con.executemany(
            "INSERT INTO rooms(name,capacity,room_type,accessible,features_json,maintenance_json) VALUES(?,?,?,?,?,?)",
            [(n, c, t, a, json.dumps(f), json.dumps(m)) for n, c, t, a, f, m in rooms],
        )
        sessions = json.loads((ROOT / "exports" / "schedule.json").read_text())["sessions"]
        details = {"CS201": "Data Structures", "MA102": "Discrete Mathematics", "EC210": "Digital Systems",
                   "CS305": "Operating Systems", "HU110": "Professional Communication", "EC302": "Microprocessors",
                   "CS220": "Database Systems", "MA205": "Probability & Statistics", "EC202": "Signals & Systems",
                   "CS401": "Cloud Computing", "EC415": "Embedded Systems Lab", "HU205": "Ethics & Society"}
        con.executemany(
            "INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?)",
            [(s["sessionId"], s["courseCode"], details.get(s["courseCode"], s["courseCode"]),
              "Assigned faculty", "Assigned group", s["day"], s["startPeriod"], s["room"]) for s in sessions],
        )
        con.executemany("INSERT OR REPLACE INTO settings(key,value_json) VALUES(?,?)",
                        [("booking_priority", json.dumps(PRIORITY)),
                         ("schedule_revision", json.dumps({"id": "REV-001", "moved": 0}))])
        audit(con, 1, "demo_seeded", "system", "seed", {"reset": reset})
        con.commit()
    con.close()


def json_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length > 1_000_000:
        raise ValueError("payload too large")
    return json.loads(handler.rfile.read(length) or b"{}")


def response(handler, status, value):
    raw = json.dumps(value, separators=(",", ":")).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    handler.end_headers()
    handler.wfile.write(raw)


def client_ip(handler):
    return handler.client_address[0]


def secure_transport(handler):
    if ENV != "production":
        return True
    return handler.headers.get("X-Forwarded-Proto", "").lower() == "https"


def current_user(handler):
    token = handler.headers.get("Authorization", "")
    if not token.startswith("Bearer "):
        return None
    raw_token = token[7:].strip()
    if len(raw_token) < 40:
        return None
    con = db()
    row = con.execute(
        """SELECT u.* FROM auth_sessions s JOIN users u ON u.id=s.user_id
           WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>? AND u.active=1 AND u.status='active'""",
        (token_hash(raw_token), int(time.time())),
    ).fetchone()
    con.close()
    return row


def login_allowed(con, identity, ip):
    cutoff = int(time.time()) - 900
    row = con.execute(
        "SELECT COUNT(*) FROM auth_attempts WHERE created_at>? AND succeeded=0 AND (identity=? OR ip=?)",
        (cutoff, identity, ip),
    ).fetchone()
    return row[0] < MAX_LOGIN_ATTEMPTS


def add_login_attempt(con, identity, ip, succeeded):
    con.execute("INSERT INTO auth_attempts(identity,ip,succeeded,created_at) VALUES(?,?,?,?)",
                (identity, ip, 1 if succeeded else 0, int(time.time())))
    con.execute("DELETE FROM auth_attempts WHERE created_at<?", (int(time.time()) - 86400,))


def validate_booking(body):
    required = ("title", "kind", "room", "day", "start_period")
    if any(not body.get(key) for key in required):
        return "title, kind, room, day and start_period are required"
    if not isinstance(body["title"], str) or not 3 <= len(body["title"].strip()) <= 160:
        return "title must be between 3 and 160 characters"
    if body["kind"] not in KINDS:
        return "kind is not allowed"
    if body["day"] not in DAYS or body["start_period"] not in TIMES:
        return "day or start_period is not allowed"
    try:
        duration = int(body.get("duration", 1))
    except (TypeError, ValueError):
        return "duration must be an integer"
    if not 1 <= duration <= 8:
        return "duration must be between 1 and 8 periods"
    return None


def booking_conflict(con, booking):
    if con.execute(
        """SELECT 1 FROM sessions WHERE room=? AND day=? AND start_period=? LIMIT 1""",
        (booking["room"], booking["day"], booking["start_period"]),
    ).fetchone():
        return "Conflicts with a scheduled class."
    room = con.execute("SELECT maintenance_json FROM rooms WHERE name=?", (booking["room"],)).fetchone()
    if room:
        for window in json.loads(room["maintenance_json"]):
            if window.get("day") == booking["day"] and window.get("start") <= booking["start_period"] <= window.get("end"):
                return "Room is in a maintenance window."
    duplicate_query = """SELECT 1 FROM bookings WHERE room=? AND day=? AND start_period=?
                         AND status IN ('pending','approved')"""
    duplicate_params = [booking["room"], booking["day"], booking["start_period"]]
    if "id" in booking.keys() and booking["id"]:
        duplicate_query += " AND id != ?"
        duplicate_params.append(booking["id"])
    duplicate_query += " LIMIT 1"
    if con.execute(duplicate_query, duplicate_params).fetchone():
        return "Room/time is already reserved by another active request."
    return None


class API(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return response(self, 200, {"ok": True, "environment": ENV, "database": DB_PATH.name})
        if not secure_transport(self):
            return response(self, 400, {"error": "https_required"})
        user = current_user(self)
        if not user:
            return response(self, 401, {"error": "authentication_required"})
        con = db()
        try:
            if path == "/api/me":
                return response(self, 200, {"id": user["id"], "email": user["email"], "name": user["display_name"],
                                             "role": user["role"], "department": user["department"]})
            if path == "/api/rooms":
                rows = con.execute("SELECT * FROM rooms ORDER BY name").fetchall()
                return response(self, 200, [{"name": r["name"], "capacity": r["capacity"], "type": r["room_type"],
                    "accessible": bool(r["accessible"]), "features": json.loads(r["features_json"]),
                    "maintenance": json.loads(r["maintenance_json"])} for r in rows])
            if path == "/api/timetable":
                rows = con.execute("SELECT * FROM sessions ORDER BY day,start_period").fetchall()
                if user["role"] == "faculty":
                    rows = [r for r in rows if r["faculty"] == user["display_name"]]
                return response(self, 200, [dict(r) for r in rows])
            if path == "/api/bookings":
                query = """SELECT b.*,u.display_name requester FROM bookings b
                           JOIN users u ON u.id=b.requester_id"""
                params = []
                if user["role"] == "club":
                    query += " WHERE b.requester_id=?"; params.append(user["id"])
                elif user["role"] == "faculty":
                    query += " WHERE b.requester_id=?"; params.append(user["id"])
                elif user["role"] == "coordinator":
                    query += " WHERE u.department=?"; params.append(user["department"])
                query += " ORDER BY b.created_at DESC"
                return response(self, 200, [dict(r) for r in con.execute(query, params).fetchall()])
            if path == "/api/audit":
                if user["role"] != "admin":
                    return response(self, 403, {"error": "admin_required"})
                return response(self, 200, [dict(r) for r in con.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 100").fetchall()])
            if path == "/api/admin/users":
                if user["role"] != "admin":
                    return response(self, 403, {"error": "admin_required"})
                return response(self, 200, [dict(r) for r in con.execute("SELECT id,email,display_name,role,department,status,created_at FROM users ORDER BY id").fetchall()])
            return response(self, 404, {"error": "not_found"})
        finally:
            con.close()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = json_body(self)
        except (ValueError, json.JSONDecodeError):
            return response(self, 400, {"error": "invalid_json"})
        if path == "/api/auth/login":
            identity = str(body.get("email", "")).lower().strip()
            ip = client_ip(self)
            con = db()
            if not login_allowed(con, identity, ip):
                con.close()
                return response(self, 429, {"error": "too_many_attempts", "retryAfter": 900})
            user = con.execute("SELECT * FROM users WHERE email=?", (identity,)).fetchone()
            valid = bool(user and user["status"] == "active" and password_ok(str(body.get("password", "")), user["password_hash"]))
            add_login_attempt(con, identity, ip, valid)
            if not valid:
                con.commit(); con.close()
                return response(self, 401, {"error": "invalid_credentials_or_pending_account"})
            raw_token = secrets.token_urlsafe(32)
            con.execute("INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES(?,?,?)",
                        (token_hash(raw_token), user["id"], int(time.time()) + SESSION_TTL))
            audit(con, user["id"], "login", "user", str(user["id"]), {"ip": ip})
            con.commit(); con.close()
            return response(self, 200, {"token": raw_token, "expiresIn": SESSION_TTL,
                                        "user": {"id": user["id"], "name": user["display_name"], "role": user["role"]}})
        if path == "/api/auth/signup":
            email = str(body.get("email", "")).lower().strip()
            role = body.get("role")
            password = str(body.get("password", ""))
            display_name = str(body.get("display_name", "")).strip()
            if not EMAIL_RE.match(email) or role not in {"coordinator", "faculty", "club"} or not 2 <= len(display_name) <= 120:
                return response(self, 422, {"error": "verified email and non-admin role are required"})
            if len(password) < 12:
                return response(self, 422, {"error": "password must be at least 12 characters"})
            con = db()
            try:
                con.execute("INSERT INTO users(email,display_name,role,department,password_hash,status,active) VALUES(?,?,?,?,?,?,?)",
                             (email, display_name, role, body.get("department"),
                              password_hash(password), "pending", 1))
                audit(con, None, "signup_pending", "user", email, {"role": role})
                con.commit()
            except sqlite3.IntegrityError:
                con.rollback(); return response(self, 409, {"error": "account_already_exists"})
            finally:
                con.close()
            return response(self, 202, {"status": "pending", "message": "An administrator must approve this account before sign-in."})
        if not secure_transport(self):
            return response(self, 400, {"error": "https_required"})
        user = current_user(self)
        if not user:
            return response(self, 401, {"error": "authentication_required"})
        con = db()
        try:
            if path == "/api/auth/logout":
                raw = self.headers.get("Authorization", "")[7:].strip()
                con.execute("UPDATE auth_sessions SET revoked_at=? WHERE token_hash=?", (int(time.time()), token_hash(raw)))
                audit(con, user["id"], "logout", "user", str(user["id"]), {})
                con.commit()
                return response(self, 200, {"ok": True})
            if path == "/api/bookings":
                error = validate_booking(body)
                if error:
                    return response(self, 422, {"error": error})
                room = con.execute("SELECT * FROM rooms WHERE name=?", (body["room"],)).fetchone()
                if not room:
                    return response(self, 422, {"error": "room_not_found"})
                con.execute("BEGIN IMMEDIATE")
                candidate = {**body, "room": room["name"]}
                conflict = booking_conflict(con, candidate)
                status = "rejected" if conflict else "pending"
                reason = conflict or "Request received; policy and conflict checks passed. Awaiting authorized approval."
                bid = "BK-" + secrets.token_hex(4).upper()
                con.execute("INSERT INTO bookings(id,title,requester_id,kind,room,day,start_period,duration,status,decision_reason) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (bid, body["title"].strip(), user["id"], body["kind"], body["room"], body["day"], body["start_period"],
                             int(body.get("duration", 1)), status, reason))
                audit(con, user["id"], "booking_created", "booking", bid, {"status": status, "kind": body["kind"]})
                con.commit()
                return response(self, 201, {"id": bid, "status": status, "reason": reason})
            if path.startswith("/api/bookings/") and path.endswith("/decision"):
                if user["role"] != "admin":
                    return response(self, 403, {"error": "admin_approval_required"})
                bid = path.split("/")[3]
                con.execute("BEGIN IMMEDIATE")
                booking = con.execute("SELECT * FROM bookings WHERE id=?", (bid,)).fetchone()
                if not booking:
                    con.rollback(); return response(self, 404, {"error": "booking_not_found"})
                if booking["requester_id"] == user["id"]:
                    con.rollback(); return response(self, 403, {"error": "cannot_approve_own_request"})
                decision = body.get("decision")
                if decision not in ("approved", "rejected"):
                    con.rollback(); return response(self, 422, {"error": "decision_must_be_approved_or_rejected"})
                if decision == "approved":
                    conflict = booking_conflict(con, booking)
                    if conflict:
                        con.rollback(); return response(self, 409, {"error": conflict})
                reason = str(body.get("reason", "Admin decision recorded."))[:300]
                con.execute("UPDATE bookings SET status=?,decision_reason=?,decided_by=? WHERE id=?",
                            (decision, reason, user["id"], bid))
                audit(con, user["id"], "booking_decided", "booking", bid, {"decision": decision})
                con.commit()
                return response(self, 200, {"id": bid, "status": decision, "reason": reason})
            if path.startswith("/api/admin/users/") and path.endswith("/approve"):
                if user["role"] != "admin":
                    return response(self, 403, {"error": "admin_required"})
                target = path.split("/")[4]
                if str(user["id"]) == target:
                    return response(self, 403, {"error": "cannot_approve_own_account"})
                con.execute("UPDATE users SET status='active',approved_by=?,active=1 WHERE id=? AND status='pending'", (user["id"], target))
                audit(con, user["id"], "user_approved", "user", target, {})
                con.commit()
                return response(self, 200, {"ok": True})
            if path.startswith("/api/bookings/") and path.endswith("/cancel"):
                bid = path.split("/")[3]
                booking = con.execute("SELECT * FROM bookings WHERE id=?", (bid,)).fetchone()
                if not booking or booking["requester_id"] != user["id"]:
                    return response(self, 403, {"error": "only_the_requester_can_cancel"})
                con.execute("UPDATE bookings SET status='cancelled',decision_reason=? WHERE id=?", ("Cancelled by requester.", bid))
                audit(con, user["id"], "booking_cancelled", "booking", bid, {})
                con.commit()
                return response(self, 200, {"ok": True})
            if path == "/api/admin/reset":
                if user["role"] != "admin":
                    return response(self, 403, {"error": "admin_required"})
                seed(reset=True)
                return response(self, 200, {"ok": True})
            return response(self, 404, {"error": "not_found"})
        except sqlite3.Error:
            con.rollback()
            return response(self, 500, {"error": "database_operation_failed"})
        finally:
            con.close()


def main():
    seed()
    port = int(os.environ.get("PORT", "8080"))
    bind = os.environ.get("ORBIT_BIND", "127.0.0.1" if ENV != "production" else "0.0.0.0")
    print(f"Orbit API listening on http://{bind}:{port}")
    ThreadingHTTPServer((bind, port), API).serve_forever()


if __name__ == "__main__":
    main()
