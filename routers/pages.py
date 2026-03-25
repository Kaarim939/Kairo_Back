from fastapi import APIRouter, HTTPException, UploadFile, File
from models.schemas import UpdatePage, ReorderPages
from services.firebase import (
    get_chapter_pages,
    update_page,
    create_page,
    delete_page,
    reorder_pages,
    upload_page_image,
)

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


@router.post("")
async def create_page_endpoint(book_id: str, chapter_id: int, file: UploadFile = File(...)):
    """Upload an image file and create a new page in the chapter."""
    contents = await file.read()
    content_type = file.content_type or "image/png"
    image_url = upload_page_image(book_id, chapter_id, contents, content_type)
    page = create_page(book_id, chapter_id, image_url)
    if page is None:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return page


@router.delete("/{page_id}")
def delete_page_endpoint(book_id: str, chapter_id: int, page_id: str):
    """Delete a page only if it has no panels."""
    result = delete_page(book_id, chapter_id, page_id)
    if result is True:
        return {"ok": True}
    raise HTTPException(status_code=400, detail=result)


@router.post("/reorder")
def reorder_pages_endpoint(book_id: str, chapter_id: int, data: ReorderPages):
    """Reorder pages by updating their pageNumber values."""
    if not reorder_pages(book_id, chapter_id, data.pages):
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"ok": True}


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
