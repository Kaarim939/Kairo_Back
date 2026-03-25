import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Read-only methods don't need auth
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Simple code-based auth for write endpoints.

    GET requests are always allowed (public read).
    PATCH/POST/PUT/DELETE require an `Authorization: Bearer <code>` header
    matching the AUTH_CODE env variable.
    """

    # Paths that use their own auth (Firebase tokens, OAuth callbacks)
    EXEMPT_PREFIXES = ("/api/auth/",)

    async def dispatch(self, request: Request, call_next):
        if request.method in SAFE_METHODS:
            return await call_next(request)

        # Skip code-based auth for user auth endpoints
        if any(request.url.path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)

        auth_code = os.getenv("AUTH_CODE", "password123")
        header = request.headers.get("Authorization", "")

        if not header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authorization code"},
            )

        provided_code = header[7:]  # Strip "Bearer "
        if provided_code != auth_code:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid authorization code"},
            )

        return await call_next(request)
