from fastapi import APIRouter, HTTPException
from models.schemas import UpdatePage
from services.firebase import get_chapter_pages, update_page

router = APIRouter(
    prefix="/books/{book_id}/chapters/{chapter_id}/pages",
    tags=["pages"],
)


@router.get("")
def list_pages(book_id: str, chapter_id: int):
    """Get all pages for a chapter."""
    pages = get_chapter_pages(book_id, chapter_id)
    if pages is None:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return pages


@router.patch("/{page_id}")
def patch_page(book_id: str, chapter_id: int, page_id: str, data: UpdatePage):
    """Update a single page (panels, dimensions).

    This is the optimized save endpoint — the editor sends only the
    changed page instead of the entire chapter.
    """
    update_data = data.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Convert panels to dicts for Firestore
    if "panels" in update_data:
        update_data["panels"] = [
            p if isinstance(p, dict) else p.model_dump() for p in update_data["panels"]
        ]

    if not update_page(book_id, chapter_id, page_id, update_data):
        raise HTTPException(status_code=404, detail="Page not found")
    return {"ok": True}
