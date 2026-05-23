from firebase_admin import auth, firestore
from services.firebase import get_db


def verify_firebase_token(id_token: str) -> dict | None:
    """Verify a Firebase ID token and return the decoded token."""
    try:
        return auth.verify_id_token(id_token)
    except Exception:
        return None


def get_user_profile(uid: str) -> dict | None:
    """Get user profile from Firestore."""
    db = get_db()
    doc = db.collection("users").document(uid).get()
    if not doc.exists:
        return None
    profile = doc.to_dict()
    profile["uid"] = uid
    return profile


def create_user_profile(uid: str, username: str, email: str) -> dict:
    """Create a user profile in Firestore."""
    db = get_db()
    profile = {
        "username": username,
        "email": email,
        "patreonId": None,
        "patreonActive": False,
        "isAdmin": False,
    }
    db.collection("users").document(uid).set(profile)
    return {**profile, "uid": uid}


def update_user_profile(uid: str, data: dict) -> bool:
    db = get_db()
    ref = db.collection("users").document(uid)
    if not ref.get().exists:
        return False
    ref.update(data)
    return True
