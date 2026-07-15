import os
import json
import base64
import uuid
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


def _to_localized(val) -> dict:
    """Convert a string or dict to a localized {en, fr, es} object."""
    if isinstance(val, dict):
        return {lang: val.get(lang, "") for lang in ("en", "fr", "es")}
    if isinstance(val, str):
        return {"en": val, "fr": "", "es": ""}
    return {"en": "", "fr": "", "es": ""}


def _normalize_book(book: dict) -> dict:
    """Ensure book has localized title/description."""
    book["title"] = _to_localized(book.get("title", ""))
    book["description"] = _to_localized(book.get("description", ""))
    return book


def _normalize_chapter(ch: dict) -> dict:
    """Ensure chapter has localized name."""
    ch["name"] = _to_localized(ch.get("name", ch.get("title", "")))
    ch.setdefault("hasColored", False)
    return ch


def get_all_books() -> list[dict]:
    db = get_db()
    books = []
    for doc in db.collection("books").stream():
        book = doc.to_dict()
        book["id"] = doc.id
        book.setdefault("visible", True)
        book.setdefault("order", 0)
        _normalize_book(book)

        # Get chapters metadata
        chapters = []
        for ch_doc in db.collection("books").document(doc.id).collection("chapters").stream():
            ch = ch_doc.to_dict()
            ch["id"] = int(ch_doc.id)
            _normalize_chapter(ch)
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
    book.setdefault("visible", True)
    book.setdefault("order", 0)
    _normalize_book(book)

    chapters = []
    for ch_doc in db.collection("books").document(book_id).collection("chapters").stream():
        ch = ch_doc.to_dict()
        ch["id"] = int(ch_doc.id)
        _normalize_chapter(ch)
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
    _normalize_chapter(ch)
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
        "title": data.get("title", {"en": "New Book", "fr": "", "es": ""}),
        "author": "Unknown",
        "description": {"en": "", "fr": "", "es": ""},
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


def delete_chapter(book_id: str, chapter_id: int) -> bool | str:
    """Delete a chapter only if it has 0 pages. Returns True on success, error string on failure."""
    db = get_db()
    ch_ref = (
        db.collection("books")
        .document(book_id)
        .collection("chapters")
        .document(str(chapter_id))
    )
    if not ch_ref.get().exists:
        return "Chapter not found"
    pages = list(ch_ref.collection("pages").limit(1).stream())
    if pages:
        return "Cannot delete a chapter that has pages"
    ch_ref.delete()
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
        "name": data.get("name", {"en": "", "fr": "", "es": ""}),
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


def create_page(book_id: str, chapter_id: int, image_url: str) -> dict | None:
    """Create a new page in a chapter. Returns the created page dict."""
    db = get_db()
    ch_ref = (
        db.collection("books")
        .document(book_id)
        .collection("chapters")
        .document(str(chapter_id))
    )
    if not ch_ref.get().exists:
        return None
    # Find next page number
    existing = list(ch_ref.collection("pages").stream())
    next_num = max((p.to_dict().get("pageNumber", 0) for p in existing), default=0) + 1
    page_id = str(uuid.uuid4())[:8]
    default_panel = {
        "id": str(uuid.uuid4())[:8],
        "x": 0,
        "y": 0,
        "width": 1,
        "height": 1,
        "texts": [],
    }
    page_data = {
        "pageNumber": next_num,
        "imageUrl": image_url,
        "panels": [default_panel],
    }
    ch_ref.collection("pages").document(page_id).set(page_data)
    return {**page_data, "id": page_id}


def delete_page(book_id: str, chapter_id: int, page_id: str) -> bool | str:
    """Delete a page only if it has no panels with texts."""
    db = get_db()
    ref = (
        db.collection("books")
        .document(book_id)
        .collection("chapters")
        .document(str(chapter_id))
        .collection("pages")
        .document(page_id)
    )
    doc = ref.get()
    if not doc.exists:
        return "Page not found"
    page = doc.to_dict()
    panels = page.get("panels", [])
    if panels and len(panels) > 0:
        # Allow deletion if the only panel is the default full-page panel with no texts
        is_default = (
            len(panels) == 1
            and panels[0].get("x", 0) == 0
            and panels[0].get("y", 0) == 0
            and panels[0].get("width", 0) == 1
            and panels[0].get("height", 0) == 1
            and not panels[0].get("texts")
        )
        if not is_default:
            has_texts = any(
                p.get("texts") and len(p.get("texts", [])) > 0
                for p in panels
            )
            if has_texts:
                return "Cannot delete a page that has texts"
            return "Cannot delete a page that has custom panels"
    ref.delete()
    return True


def reorder_pages(book_id: str, chapter_id: int, page_orders: list[dict]) -> bool:
    """Update pageNumber for multiple pages. page_orders = [{"id": "xxx", "pageNumber": 1}, ...]"""
    db = get_db()
    ch_ref = (
        db.collection("books")
        .document(book_id)
        .collection("chapters")
        .document(str(chapter_id))
    )
    if not ch_ref.get().exists:
        return False
    for po in page_orders:
        ch_ref.collection("pages").document(po["id"]).update({"pageNumber": po["pageNumber"]})
    return True


def upload_asset(book_id: str, file_bytes: bytes, content_type: str) -> str | None:
    """Upload a generic asset (volume cover, character portrait) for a book and return the public URL.

    Returns None if the book does not exist. Does not mutate the book document — the URL is wired
    into volumes/characters via the regular book PATCH path.
    """
    db = get_db()
    if not db.collection("books").document(book_id).get().exists:
        return None
    bucket = storage.bucket()
    ext = content_type.split("/")[-1] if "/" in content_type else "png"
    filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    blob = bucket.blob(f"mangas/{book_id}/assets/{filename}")
    blob.upload_from_string(file_bytes, content_type=content_type)
    blob.make_public()
    return blob.public_url


def upload_page_image(book_id: str, chapter_id: int, file_bytes: bytes, content_type: str) -> str:
    """Upload a page image to Firebase Storage and return the public URL."""
    import uuid as _uuid
    db = get_db()  # ensure initialized
    bucket = storage.bucket()
    ext = content_type.split("/")[-1] if "/" in content_type else "png"
    filename = f"{_uuid.uuid4().hex[:12]}.{ext}"
    blob = bucket.blob(f"mangas/{book_id}/{chapter_id}/{filename}")
    blob.upload_from_string(file_bytes, content_type=content_type)
    blob.make_public()
    return blob.public_url


def replace_page_image(
    book_id: str, chapter_id: int, page_id: str, file_bytes: bytes, content_type: str
) -> str | None:
    """Replace only the imageUrl of an existing page. Panels and texts are untouched."""
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
        return None
    image_url = upload_page_image(book_id, chapter_id, file_bytes, content_type)
    ref.update({"imageUrl": image_url})
    return image_url


def set_colored_page_image(
    book_id: str, chapter_id: int, page_id: str, file_bytes: bytes, content_type: str
) -> str | None:
    """Upload/replace the colored variant image of an existing page.

    Panels and texts are shared with the normal image and left untouched.
    """
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
        return None
    image_url = upload_page_image(book_id, chapter_id, file_bytes, content_type)
    ref.update({"coloredImageUrl": image_url})
    return image_url


def remove_colored_page_image(book_id: str, chapter_id: int, page_id: str) -> bool:
    """Clear the colored variant of a page (falls back to the normal image)."""
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
    ref.update({"coloredImageUrl": None})
    return True


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
