from fastapi import APIRouter, HTTPException, Request
from models.auth_schemas import RegisterRequest
from services.auth import (
    verify_firebase_token,
    get_user_profile,
    create_user_profile,
)
from firebase_admin import auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register(data: RegisterRequest):
    """Register a new user via Firebase Auth + Firestore profile."""
    try:
        user = auth.create_user(
            email=data.email,
            password=data.password,
            display_name=data.username,
        )
    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=409, detail="Email already exists")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    profile = create_user_profile(user.uid, data.username, data.email)
    return {"ok": True, "uid": user.uid, "profile": profile}


@router.get("/me")
def get_me(request: Request):
    """Get current user profile from Firebase token."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = header[7:]
    decoded = verify_firebase_token(token)
    if not decoded:
        raise HTTPException(status_code=401, detail="Invalid token")

    profile = get_user_profile(decoded["uid"])
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return profile
