import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "bput").strip()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

REPORT_OUTPUT_DIR = Path(os.getenv("REPORT_OUTPUT_DIR", "generated_reports"))
SIGNED_URL_SECONDS = int(os.getenv("SIGNED_URL_SECONDS", "604800"))

def validate_config():
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if missing:
        raise RuntimeError(
            "Missing configuration values: " + ", ".join(missing) +
            ". Fill in your .env file using .env.example."
        )
