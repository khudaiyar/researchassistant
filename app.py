from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_cors import CORS
from database import init_db, seed_db, seed_admin, get_conn
from agent import run_agent
from auth import auth_bp, bcrypt
import traceback
import secrets
import os

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app, supports_credentials=True)
bcrypt.init_app(app)
app.register_blueprint(auth_bp)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data    = request.get_json(silent=True) or {}
    query   = data.get("message", "").strip()
    history = data.get("history", [])
    if not query:
        return jsonify({"error": "Empty message"}), 400
    try:
        answer, thoughts, downloaded = run_agent(query, history=history)
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO search_history (query, response) VALUES (%s, %s)",
                (query, answer),
            )
        conn.commit()
        conn.close()
        resp = {"answer": answer, "thoughts": thoughts}
        if downloaded:
            resp["download_url"] = f"/api/serve-download/{downloaded}"
        return jsonify(resp)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def stats():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM papers")
        papers = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM researchers")
        researchers = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM search_history")
        queries = cur.fetchone()["cnt"]
    conn.close()
    return jsonify({"papers": papers, "researchers": researchers, "queries": queries})


@app.route("/api/papers")
def papers():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, authors, year, venue, doi, url "
            "FROM papers ORDER BY created_at DESC LIMIT 20"
        )
        rows = cur.fetchall()
    conn.close()
    return jsonify(rows)


@app.route("/api/researchers")
def researchers():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, affiliation, research_area "
            "FROM researchers ORDER BY name"
        )
        rows = cur.fetchall()
    conn.close()
    return jsonify(rows)


@app.route("/api/serve-download/<path:filename>")
def serve_download(filename):
    return send_from_directory(DOWNLOADS_DIR, filename, as_attachment=True)


@app.route("/api/downloads")
def downloads():
    files = []
    if os.path.exists(DOWNLOADS_DIR):
        for fname in sorted(os.listdir(DOWNLOADS_DIR)):
            if fname.lower().endswith(".pdf"):
                fpath = os.path.join(DOWNLOADS_DIR, fname)
                size_kb = os.path.getsize(fpath) // 1024
                files.append({"name": fname, "size_kb": size_kb})
    return jsonify(files)


@app.route("/admin")
def admin_page():
    if not session.get("is_admin"):
        return render_template("index.html")
    return render_template("admin.html")


if __name__ == "__main__":
    init_db()
    seed_db()
    seed_admin(bcrypt)
    print("\n  Friday is running → http://localhost:5050\n")
    app.run(debug=True, port=5050)
