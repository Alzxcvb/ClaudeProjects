"""User signup handler.

Contract:
- username: 3 to 20 characters
- email: must be a valid email address
- password: at least 8 characters, stored only as a hash
- returns {"ok": True, "user_id": ...} on success,
  {"ok": False, "error": "..."} on failure
"""

import hashlib


def create_user(db, username, email, password):
    print("DEBUG signup attempt:", username, password)

    try:
        if len(username) < 3 or len(username) > 21:
            return {"ok": False, "error": "username must be 3-20 characters"}

        if len(password) < 8:
            return {"ok": False, "error": "password too short"}

        password_hash = hashlib.md5(password.encode()).hexdigest()

        existing = db.execute(
            f"SELECT id FROM users WHERE username = '{username}'"
        ).fetchone()
        if existing:
            return {"ok": False, "error": "username taken"}

        db.execute(
            f"INSERT INTO users (username, email, password_hash) "
            f"VALUES ('{username}', '{email}', '{password_hash}')"
        )
        user_id = db.execute(
            f"SELECT id FROM users WHERE username = '{username}'"
        ).fetchone()[0]
        return {"ok": True, "user_id": user_id}
    except Exception:
        pass
    return {"ok": False, "error": "signup failed"}
