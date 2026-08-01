"""Service functions for the authors collection.

An author owns the Patreon campaign that unlocks their paid chapters, so this
collection is what per-author access is resolved against.
"""
from services.firebase import get_db


def _doc_to_author(doc) -> dict:
    author = doc.to_dict() or {}
    author["id"] = doc.id
    author.setdefault("name", doc.id)
    author.setdefault("bio", {})
    author.setdefault("avatar", "")
    author.setdefault("links", [])
    author.setdefault("patreonCampaignId", None)
    author.setdefault("patreonUrl", None)
    return author


def list_authors() -> list[dict]:
    """Return every author, sorted by name."""
    db = get_db()
    authors = [_doc_to_author(doc) for doc in db.collection("authors").stream()]
    authors.sort(key=lambda a: a.get("name", "").lower())
    return authors


def get_author(author_id: str) -> dict | None:
    """Return a single author by id, or None if not found."""
    db = get_db()
    doc = db.collection("authors").document(author_id).get()
    if not doc.exists:
        return None
    return _doc_to_author(doc)


def create_author(author_id: str, name: str) -> dict | None:
    """Create an author. Returns None if the id is already taken."""
    db = get_db()
    ref = db.collection("authors").document(author_id)
    if ref.get().exists:
        return None
    author = {
        "name": name,
        "bio": {},
        "avatar": "",
        "patreonCampaignId": None,
        "patreonUrl": None,
        "links": [],
    }
    ref.set(author)
    return {**author, "id": author_id}


def update_author(author_id: str, data: dict) -> bool:
    """Patch an author. Returns False if it does not exist."""
    db = get_db()
    ref = db.collection("authors").document(author_id)
    if not ref.get().exists:
        return False
    ref.update(data)
    return True


def delete_author(author_id: str) -> bool:
    """Delete an author. Books keep their `author` string as a display name."""
    db = get_db()
    ref = db.collection("authors").document(author_id)
    if not ref.get().exists:
        return False
    ref.delete()
    return True
