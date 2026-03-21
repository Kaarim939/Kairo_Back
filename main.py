import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers import books, chapters, pages, imports
from middleware.auth import AuthMiddleware

load_dotenv()

app = FastAPI(title="Kairo API", version="0.1.0")

# CORS — restrict to known origins
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "PATCH", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# Auth — simple code-based auth for write endpoints
app.add_middleware(AuthMiddleware)

app.include_router(books.router, prefix="/api")
app.include_router(chapters.router, prefix="/api")
app.include_router(pages.router, prefix="/api")
app.include_router(imports.router, prefix="/api")


@app.get("/")
def root():
    return {"name": "Kairo API", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug/creds")
def debug_creds():
    """Temporary endpoint to verify credentials loading. DELETE AFTER DEBUGGING."""
    import base64
    cred_b64 = os.getenv("FIREBASE_CREDENTIALS_BASE64", "")
    cred_json_raw = os.getenv("FIREBASE_CREDENTIALS_JSON", "")

    result = {"has_base64": bool(cred_b64), "has_json": bool(cred_json_raw)}

    if cred_b64:
        try:
            decoded = json.loads(base64.b64decode(cred_b64))
            result["base64_keys"] = list(decoded.keys())
            result["project_id"] = decoded.get("project_id", "MISSING")
            result["has_private_key"] = "private_key" in decoded
            result["private_key_starts"] = decoded.get("private_key", "")[:30]
            result["private_key_length"] = len(decoded.get("private_key", ""))
        except Exception as e:
            result["base64_error"] = str(e)

    if cred_json_raw:
        try:
            parsed = json.loads(cred_json_raw)
            result["json_keys"] = list(parsed.keys())
        except Exception as e:
            result["json_error"] = str(e)

    return result
