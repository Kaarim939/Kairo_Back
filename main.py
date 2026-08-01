import os
import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from dotenv import load_dotenv
from routers import books, chapters, pages, imports, user_auth, patreon, osts, authors
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
    allow_methods=["GET", "PATCH", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Auth — simple code-based auth for write endpoints
app.add_middleware(AuthMiddleware)

app.include_router(books.router, prefix="/api")
app.include_router(chapters.router, prefix="/api")
app.include_router(pages.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(user_auth.router, prefix="/api")
app.include_router(patreon.router, prefix="/api")
app.include_router(authors.router, prefix="/api")
app.include_router(osts.router, prefix="/api")


@app.get("/")
def root():
    return {"name": "Kairo API", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/image-proxy")
async def image_proxy(url: str = Query(...)):
    # Only allow proxying Firebase Storage URLs
    if not url.startswith("https://storage.googleapis.com/") and not url.startswith("https://firebasestorage.googleapis.com/"):
        return Response(status_code=403, content="Forbidden")
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
    return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/png"))


