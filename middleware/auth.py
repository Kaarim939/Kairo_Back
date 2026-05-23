from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from services.auth import verify_firebase_token, get_user_profile

# Read-only methods don't need auth
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Firebase-token auth for write endpoints.

    GET/HEAD/OPTIONS are always allowed (public read).
    PATCH/POST/PUT/DELETE require an `Authorization: Bearer <firebase_id_token>`
    header. The token is verified, the user's Firestore profile is looked up,
    and the request is allowed only if `profile.isAdmin is True`.

    /api/auth/* endpoints handle their own token verification internally and
    are exempted here.
    """

    # Paths that use their own auth (Firebase tokens, OAuth callbacks)
    EXEMPT_PREFIXES = ("/api/auth/",)

    async def dispatch(self, request: Request, call_next):
        if request.method in SAFE_METHODS:
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)

        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing token"},
            )

        token = header[7:]  # Strip "Bearer "
        decoded = verify_firebase_token(token)
        if not decoded:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token"},
            )

        profile = get_user_profile(decoded["uid"])
        if not profile:
            return JSONResponse(
                status_code=403,
                content={"detail": "Profile not found"},
            )

        if profile.get("isAdmin") is not True:
            return JSONResponse(
                status_code=403,
                content={"detail": "Admin only"},
            )

        request.state.user = decoded
        request.state.profile = profile
        return await call_next(request)
