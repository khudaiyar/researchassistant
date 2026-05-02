import os
from dotenv import load_dotenv
load_dotenv()

# ── LLM ──────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "meta-llama/llama-4-scout-17b-16e-instruct"

# ── Admin ─────────────────────────────────────────────────────────────────────
ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL", "admin@friday.ai")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Friday@2026")

# ── MySQL ─────────────────────────────────────────────────────────────────────
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_USER     = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root1234")
DB_NAME     = os.getenv("DB_NAME", "research_assistant")
