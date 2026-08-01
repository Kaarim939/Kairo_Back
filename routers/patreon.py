import os
import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from services.auth import verify_firebase_token, update_user_profile

router = APIRouter(prefix="/auth/patreon", tags=["patreon"])

PATREON_CLIENT_ID = os.getenv("PATREON_CLIENT_ID", "")
PATREON_CLIENT_SECRET = os.getenv("PATREON_CLIENT_SECRET", "")
PATREON_REDIRECT_URI = os.getenv("PATREON_REDIRECT_URI", "")
PATREON_CAMPAIGN_ID = os.getenv("PATREON_CAMPAIGN_ID", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://kairo-reader.netlify.app")


@router.get("/link")
def patreon_link(token: str = Query(...)):
    """Start Patreon OAuth flow. Requires Firebase token as query param."""
    decoded = verify_firebase_token(token)
    if not decoded:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Build Patreon OAuth URL with state = Firebase UID
    oauth_url = (
        "https://www.patreon.com/oauth2/authorize"
        f"?response_type=code"
        f"&client_id={PATREON_CLIENT_ID}"
        f"&redirect_uri={PATREON_REDIRECT_URI}"
        f"&scope=identity%20identity.memberships"
        f"&state={decoded['uid']}"
    )
    return RedirectResponse(url=oauth_url)


@router.get("/callback")
async def patreon_callback(code: str = Query(...), state: str = Query(...)):
    """Patreon OAuth callback. State = Firebase UID."""
    uid = state

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://www.patreon.com/api/oauth2/token",
            data={
                "code": code,
                "grant_type": "authorization_code",
                "client_id": PATREON_CLIENT_ID,
                "client_secret": PATREON_CLIENT_SECRET,
                "redirect_uri": PATREON_REDIRECT_URI,
            },
        )

    if token_resp.status_code != 200:
        return RedirectResponse(url=f"{FRONTEND_URL}?patreon=error")

    access_token = token_resp.json().get("access_token")

    # Get Patreon identity + memberships with campaign info
    async with httpx.AsyncClient() as client:
        identity_resp = await client.get(
            "https://www.patreon.com/api/oauth2/v2/identity"
            "?include=memberships,memberships.campaign"
            "&fields[member]=patron_status,currently_entitled_amount_cents"
            "&fields[campaign]=vanity",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if identity_resp.status_code != 200:
        return RedirectResponse(url=f"{FRONTEND_URL}?patreon=error")

    identity_data = identity_resp.json()
    patreon_id = identity_data.get("data", {}).get("id")

    # Collect EVERY campaign this user actively backs.
    #
    # One OAuth link is enough for per-author access: the identity endpoint
    # returns all of the user's memberships, so there is no need for a separate
    # flow per author. We store the whole set and intersect it with each book's
    # campaign at read time.
    active_campaigns: list[str] = []
    for included in identity_data.get("included", []):
        if included.get("type") != "member":
            continue
        attrs = included.get("attributes", {})
        if attrs.get("patron_status") != "active_patron":
            continue
        campaign_data = (
            included.get("relationships", {}).get("campaign", {}).get("data", {})
        )
        campaign_id = campaign_data.get("id")
        if campaign_id and campaign_id not in active_campaigns:
            active_campaigns.append(campaign_id)

    # Coarse flag: backs the platform campaign, if one is configured.
    is_active = bool(PATREON_CAMPAIGN_ID) and PATREON_CAMPAIGN_ID in active_campaigns

    # Update user profile
    update_user_profile(uid, {
        "patreonId": patreon_id,
        "patreonActive": is_active,
        "patreonCampaigns": active_campaigns,
    })

    return RedirectResponse(url=f"{FRONTEND_URL}?patreon={'linked' if is_active else 'inactive'}")
