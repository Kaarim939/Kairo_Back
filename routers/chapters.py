from fastapi import APIRouter, HTTPException
from models.schemas import UpdateChapterMeta
from services.firebase import (
    get_chapter_meta,
    get_chapter_pages,
    update_chapter_meta,
)

router = APIRouter(prefix="/books/{book_id}/chapters", tags=["chapters"])


@router.get("/{chapter_id}")
def read_chapter(book_id: str, chapter_id: int):
    """Get full chapter with pages, panels, texts."""
    meta = get_chapter_meta(book_id, chapter_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Chapter not found")
    pages = get_chapter_pages(book_id, chapter_id)
    return {**meta, "pages": pages or []}


@router.patch("/{chapter_id}")
def patch_chapter(book_id: str, chapter_id: int, data: UpdateChapterMeta):
    """Update chapter metadata (not pages)."""
    update_data = data.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    if not update_chapter_meta(book_id, chapter_id, update_data):
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"ok": True}
