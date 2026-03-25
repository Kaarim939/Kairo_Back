import os
import json
import base64
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv

load_dotenv()

_db = None


def get_db() -> firestore.Client:
    global _db
    if _db is None:
        cred_path = os.getenv("FIREBASE_CREDENTIALS", "firebase-credentials.json")
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            # Try base64-encoded credentials (safest for deployment)
            cred_b64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")
            if cred_b64:
                cred_dict = json.loads(base64.b64decode(cred_b64))
                cred = credentials.Certificate(cred_dict)
            else:
                # Try raw JSON string
                cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
                if cred_json:
                    cred = credentials.Certificate(json.loads(cred_json))
                else:
                    raise RuntimeError(
                        "No Firebase credentials found. "
                        "Set FIREBASE_CREDENTIALS, FIREBASE_CREDENTIALS_BASE64, "
                        "or FIREBASE_CREDENTIALS_JSON env var."
                    )
        bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "kairo-reader.firebasestorage.app")
        firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
        _db = firestore.client()
    return _db


# --- Firestore structure ---
# books/{bookId}              → { title, author, description }
# books/{bookId}/chapters/{chapterId} → { title, free, pageWidth, pageHeight, fontSize, font, availableLanguages }
# books/{bookId}/chapters/{chapterId}/pages/{pageId} → { pageNumber, imageUrl, width?, height?, panels: [...] }


def get_all_books() -> list[dict]:
    db = get_db()
    books = []
    for doc in db.collection("books").stream():
        book = doc.to_dict()
        book["id"] = doc.id
        book.setdefault("visible", True)
        book.setdefault("order", 0)

        # Get chapters metadata
        chapters = []
        for ch_doc in db.collection("books").document(doc.id).collection("chapters").stream():
            ch = ch_doc.to_dict()
            ch["id"] = int(ch_doc.id)
            # Count pages
            pages_ref = (
                db.collection("books")
                .document(doc.id)
                .collection("chapters")
                .document(ch_doc.id)
                .collection("pages")
            )
            ch["pageCount"] = len(list(pages_ref.stream()))
            chapters.append(ch)

        chapters.sort(key=lambda c: c["id"])
        book["chapters"] = chapters

        # Cover: use stored cover, fallback to first page of first chapter
        if not book.get("cover"):
            if chapters:
                first_ch = chapters[0]
                pages_ref = (
                    db.collection("books")
                    .document(doc.id)
                    .collection("chapters")
                    .document(str(first_ch["id"]))
                    .collection("pages")
                )
                first_page = None
                for p in pages_ref.order_by("pageNumber").limit(1).stream():
                    first_page = p.to_dict()
                book["cover"] = first_page["imageUrl"] if first_page else ""
            else:
                book["cover"] = ""

        books.append(book)
    return books


def get_book(book_id: str) -> dict | None:
    db = get_db()
    doc = db.collection("books").document(book_id).get()
    if not doc.exists:
        return None
    book = doc.to_dict()
    book["id"] = doc.id

    chapters = []
    for ch_doc in db.collection("books").document(book_id).collection("chapters").stream():
        ch = ch_doc.to_dict()
        ch["id"] = int(ch_doc.id)
        pages_ref = (
            db.collection("books")
            .document(book_id)
            .collection("chapters")
            .document(ch_doc.id)
            .collection("pages")
        )
        ch["pageCount"] = len(list(pages_ref.stream()))
        chapters.append(ch)

    chapters.sort(key=lambda c: c["id"])
    book["chapters"] = chapters

    if not book.get("cover"):
        if chapters:
            first_ch = chapters[0]
            pages_ref = (
                db.collection("books")
                .document(book_id)
                .collection("chapters")
                .document(str(first_ch["id"]))
                .collection("pages")
            )
            first_page = None
            for p in pages_ref.order_by("pageNumber").limit(1).stream():
                first_page = p.to_dict()
            book["cover"] = first_page["imageUrl"] if first_page else ""
        else:
            book["cover"] = ""

    return book


def get_chapter_pages(book_id: str, chapter_id: int) -> list[dict] | None:
    db = get_db()
    ch_ref = (
        db.collection("books")
        .document(book_id)
        .collection("chapters")
        .document(str(chapter_id))
    )
    if not ch_ref.get().exists:
        return None

    pages = []
    for p_doc in ch_ref.collection("pages").order_by("pageNumber").stream():
        page = p_doc.to_dict()
        page["id"] = p_doc.id
        pages.append(page)
    return pages


def get_chapter_meta(book_id: str, chapter_id: int) -> dict | None:
    db = get_db()
    doc = (
        db.collection("books")
        .document(book_id)
        .collection("chapters")
        .document(str(chapter_id))
        .get()
    )
    if not doc.exists:
        return None
    ch = doc.to_dict()
    ch["id"] = int(doc.id)
    return ch


def create_book(book_id: str, data: dict) -> bool:
    """Create a new book with placeholder data."""
    db = get_db()
    ref = db.collection("books").document(book_id)
    if ref.get().exists:
        return False
    # Count existing books for default order
    existing_count = len(list(db.collection("books").stream()))
    ref.set({
        "title": data.get("title", "New Book"),
        "author": "Unknown",
        "description": "",
        "visible": True,
        "order": existing_count,
    })
    return True


def update_book(book_id: str, data: dict) -> bool:
    db = get_db()
    ref = db.collection("books").document(book_id)
    if not ref.get().exists:
        return False
    ref.update(data)
    return True


def update_chapter_meta(book_id: str, chapter_id: int, data: dict) -> bool:
    db = get_db()
    ref = (
        db.collection("books")
        .document(book_id)
        .collection("chapters")
        .document(str(chapter_id))
    )
    if not ref.get().exists:
        return False
    ref.update(data)
    return True


def update_page(book_id: str, chapter_id: int, page_id: str, data: dict) -> bool:
    db = get_db()
    ref = (
        db.collection("books")
        .document(book_id)
        .collection("chapters")
        .document(str(chapter_id))
        .collection("pages")
        .document(page_id)
    )
    if not ref.get().exists:
        return False
    ref.update(data)
    return True


def create_chapter(book_id: str, data: dict) -> int | None:
    """Create a new empty chapter. Returns the new chapter id."""
    db = get_db()
    book_ref = db.collection("books").document(book_id)
    if not book_ref.get().exists:
        return None
    # Find next chapter id
    existing = list(book_ref.collection("chapters").stream())
    next_id = max((int(doc.id) for doc in existing), default=0) + 1
    ch_data = {
        "number": data.get("number", float(next_id)),
        "name": data.get("name", ""),
        "free": data.get("free", False),
        "pageWidth": data.get("pageWidth", 800),
        "pageHeight": data.get("pageHeight", 1200),
        "fontSize": data.get("fontSize", 20),
        "font": data.get("font", "Arial"),
        "availableLanguages": data.get("availableLanguages", ["en"]),
    }
    book_ref.collection("chapters").document(str(next_id)).set(ch_data)
    return next_id


def upload_cover(book_id: str, file_bytes: bytes, content_type: str) -> str:
    """Upload a cover image to Firebase Storage and update the book's cover field."""
    db = get_db()  # Ensure Firebase app is initialized
    bucket = storage.bucket()
    ext = content_type.split("/")[-1] if "/" in content_type else "png"
    blob = bucket.blob(f"mangas/{book_id}/cover.{ext}")
    blob.upload_from_string(file_bytes, content_type=content_type)
    blob.make_public()
    url = blob.public_url
    db.collection("books").document(book_id).update({"cover": url})
    return url


def import_book_json(book_data: dict) -> str:
    """Import a full book from JSON (with chapters and pages)."""
    db = get_db()
    book_id = book_data["id"]

    # Write book metadata
    book_meta = {
        k: v for k, v in book_data.items() if k not in ("id", "chapters")
    }
    db.collection("books").document(book_id).set(book_meta)

    # Write chapters and pages
    for chapter in book_data.get("chapters", []):
        ch_id = str(chapter["id"])
        ch_meta = {
            k: v for k, v in chapter.items() if k not in ("id", "pages")
        }
        ch_ref = (
            db.collection("books")
            .document(book_id)
            .collection("chapters")
            .document(ch_id)
        )
        ch_ref.set(ch_meta)

        for page in chapter.get("pages", []):
            page_id = page["id"]
            page_data = {k: v for k, v in page.items() if k != "id"}
            ch_ref.collection("pages").document(page_id).set(page_data)

    return book_id
