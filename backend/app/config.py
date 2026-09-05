import os

from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.environ["RAZORPAY_KEY_ID"]
RAZORPAY_KEY_SECRET = os.environ["RAZORPAY_KEY_SECRET"]
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./agentic_commerce.db")

PORT = int(os.environ.get("PORT", "8000"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

# Not read until Phase 3 (Gemini smoke test) — left here so config stays in one place.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "")
