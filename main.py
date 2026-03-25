import os
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


