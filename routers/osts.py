"""Global OST library CRUD endpoints."""
import json
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from models.schemas import OSTRecord, UpdateOSTMeta
from services.osts import (
    list_osts,
    get_ost,
    create_ost,
    update_ost,
    delete_ost,
)

router = APIRouter(prefix="/osts", tags=["osts"])


@router.get("")
def list_all_osts() -> list[OSTRecord]:
    """Public read of all OSTs in the global library."""
    return list_osts()


@router.post("")
async def upload_ost(
    file: UploadFile = File(...),
    name: str = Form(...),
    origin: str = Form(""),
    tags: str = Form("[]"),
    duration: float = Form(0.0),
):
    """Upload an audio file with metadata. Multipart form.

    `tags` is a JSON-encoded array of strings (the frontend serializes
    its tag-chip list before POSTing).
    """
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be an audio file")
    contents = await file.read()
    if len(contents) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")
    if not name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    try:
        tags_list = json.loads(tags) if tags else []
        if not isinstance(tags_list, list) or not all(
            isinstance(t, str) for t in tags_list
        ):
            raise ValueError("tags must be a JSON array of strings")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid tags: {e}")
    if duration < 0 or duration > 36000:
        raise HTTPException(status_code=400, detail="duration out of range")
    meta = {
        "name": name.strip(),
        "origin": origin.strip(),
        "tags": tags_list,
        "duration": duration,
    }
    return create_ost(contents, file.content_type, meta)


@router.patch("/{ost_id}")
def patch_ost(ost_id: str, data: UpdateOSTMeta):
    """Update OST metadata. Cannot change the audio file."""
    update_data = data.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    if not update_ost(ost_id, update_data):
        raise HTTPException(status_code=404, detail="OST not found")
    return {"ok": True}


@router.delete("/{ost_id}")
def remove_ost(ost_id: str):
    """Delete an OST. Refuses with 409 if any page references it."""
    result = delete_ost(ost_id)
    if result is True:
        return {"ok": True}
    # result is an error string
    if "not found" in result:
        raise HTTPException(status_code=404, detail=result)
    raise HTTPException(status_code=409, detail=result)


@router.get("/{ost_id}")
def read_ost(ost_id: str):
    """Get a single OST by id."""
    ost = get_ost(ost_id)
    if not ost:
        raise HTTPException(status_code=404, detail="OST not found")
    return ost
