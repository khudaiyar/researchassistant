from flask import Blueprint, request, jsonify, session
from flask_bcrypt import Bcrypt
from database import get_conn

auth_bp = Blueprint("auth", __name__)
bcrypt  = Bcrypt()


def _admin_required():
    if not session.get("is_admin"):
        return jsonify({"error": "Admin access required."}), 403
    return None


@auth_bp.route("/auth/register", methods=["POST"])
def register():
    data     = request.get_json(silent=True) or {}
    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"error": "All fields are required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                conn.close()
                return jsonify({"error": "An account with this email already exists."}), 409
            cur.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, pw_hash),
            )
            user_id = cur.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    session["user_id"]    = user_id
    session["user_name"]  = name
    session["user_email"] = email
    session["is_admin"]   = False
    return jsonify({"message": "Account created.", "name": name, "email": email, "is_admin": False})


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    data     = request.get_json(silent=True) or {}
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, email, password_hash, is_admin FROM users WHERE email = %s",
                (email,),
            )
            user = cur.fetchone()
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if not user or not bcrypt.check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Incorrect email or password."}), 401

    session["user_id"]    = user["id"]
    session["user_name"]  = user["name"]
    session["user_email"] = user["email"]
    session["is_admin"]   = bool(user["is_admin"])
    return jsonify({
        "message":  "Signed in.",
        "name":     user["name"],
        "email":    user["email"],
        "is_admin": bool(user["is_admin"]),
    })


@auth_bp.route("/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Signed out."})


@auth_bp.route("/auth/me")
def me():
    if "user_id" in session:
        return jsonify({
            "logged_in": True,
            "name":     session["user_name"],
            "email":    session["user_email"],
            "is_admin": session.get("is_admin", False),
        })
    return jsonify({"logged_in": False})


# ── Admin API ─────────────────────────────────────────────────────────────────

@auth_bp.route("/admin/api/users")
def admin_users():
    err = _admin_required()
    if err: return err
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, email, is_admin, created_at FROM users ORDER BY created_at DESC"
        )
        users = cur.fetchall()
    conn.close()
    for u in users:
        u["created_at"] = str(u["created_at"])
        u["is_admin"]   = bool(u["is_admin"])
    return jsonify(users)


@auth_bp.route("/admin/api/users/<int:uid>", methods=["DELETE"])
def admin_delete_user(uid):
    err = _admin_required()
    if err: return err
    if uid == session.get("user_id"):
        return jsonify({"error": "Cannot delete your own admin account."}), 400
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"message": "User deleted."})


@auth_bp.route("/admin/api/users/<int:uid>/toggle-admin", methods=["POST"])
def admin_toggle(uid):
    err = _admin_required()
    if err: return err
    if uid == session.get("user_id"):
        return jsonify({"error": "Cannot change your own admin status."}), 400
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT is_admin FROM users WHERE id = %s", (uid,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "User not found."}), 404
        new_val = 0 if row["is_admin"] else 1
        cur.execute("UPDATE users SET is_admin = %s WHERE id = %s", (new_val, uid))
    conn.commit()
    conn.close()
    return jsonify({"is_admin": bool(new_val)})


@auth_bp.route("/admin/api/stats")
def admin_stats():
    err = _admin_required()
    if err: return err
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM users")
        users = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM papers")
        papers = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM researchers")
        researchers = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM search_history")
        queries = cur.fetchone()["cnt"]
    conn.close()
    return jsonify({"users": users, "papers": papers, "researchers": researchers, "queries": queries})
