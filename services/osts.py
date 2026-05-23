"""Service functions for the global OST (background music) library."""
import uuid
from datetime import datetime, timezone
from firebase_admin import firestore, storage
from services.firebase import get_db


def list_osts() -> list[dict]:
    """Return all OSTs in the library, sorted by createdAt descending."""
    db = get_db()
    osts = []
    for doc in db.collection("osts").stream():
        ost = doc.to_dict()
        ost["id"] = doc.id
        osts.append(ost)
    osts.sort(key=lambda o: o.get("createdAt", ""), reverse=True)
    return osts


def get_ost(ost_id: str) -> dict | None:
    """Return a single OST by id, or None if not found."""
    db = get_db()
    doc = db.collection("osts").document(ost_id).get()
    if not doc.exists:
        return None
    ost = doc.to_dict()
    ost["id"] = doc.id
    return ost


def create_ost(file_bytes: bytes, content_type: str, meta: dict) -> dict:
    """Upload an audio file to Storage and write the Firestore doc.

    Returns the new OST record (including id and url).
    """
    db = get_db()  # ensure Firebase app is initialized
    bucket = storage.bucket()
    ext = content_type.split("/")[-1] if "/" in content_type else "mp3"
    ost_id = uuid.uuid4().hex[:12]
    filename = f"{ost_id}.{ext}"
    blob = bucket.blob(f"osts/{filename}")
    blob.upload_from_string(file_bytes, content_type=content_type)
    blob.make_public()
    url = blob.public_url
    created_at = datetime.now(timezone.utc).isoformat()
    record = {
        "name": meta["name"],
        "origin": meta.get("origin", ""),
        "tags": meta.get("tags", []),
        "duration": float(meta.get("duration", 0)),
        "url": url,
        "createdAt": created_at,
    }
    db.collection("osts").document(ost_id).set(record)
    return {**record, "id": ost_id}


def update_ost(ost_id: str, data: dict) -> bool:
    """Partial metadata update. Returns False if the OST doesn't exist."""
    db = get_db()
    ref = db.collection("osts").document(ost_id)
    if not ref.get().exists:
        return False
    ref.update(data)
    return True


def _count_ost_usage(ost_id: str) -> int:
    """Count how many pages across all books reference this OST."""
    db = get_db()
    count = 0
    for book_doc in db.collection("books").stream():
        for ch_doc in book_doc.reference.collection("chapters").stream():
            for page_doc in ch_doc.reference.collection("pages").stream():
                page = page_doc.to_dict()
                if page.get("ostId") == ost_id:
                    count += 1
    return count


def delete_ost(ost_id: str) -> bool | str:
    """Delete an OST. Returns True on success, error string on failure.

    Refuses to delete if any page references the OST.
    """
    db = get_db()
    ref = db.collection("osts").document(ost_id)
    doc = ref.get()
    if not doc.exists:
        return "OST not found"
    usage = _count_ost_usage(ost_id)
    if usage > 0:
        return f"Used by {usage} pages"
    # Delete Storage blob
    ost = doc.to_dict()
    url = ost.get("url", "")
    if url:
        bucket = storage.bucket()
        # Extract the blob path from the public URL.
        # Public URL format: https://storage.googleapis.com/<bucket>/osts/<filename>
        # Find "osts/" in the URL and take everything from there.
        idx = url.find("/osts/")
        if idx != -1:
            blob_path = url[idx + 1:]
            try:
                bucket.blob(blob_path).delete()
            except Exception:
                # Blob may have been deleted already, or path differs; non-fatal
                pass
    ref.delete()
    return True
