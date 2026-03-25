from fastapi import APIRouter, HTTPException, UploadFile, File
from models.schemas import CreateBook, UpdateBook
from services.firebase import create_book, get_all_books, get_book, update_book, upload_cover

router = APIRouter(prefix="/books", tags=["books"])


@router.get("")
def list_books():
    """List all books with chapter metadata (no pages)."""
    return get_all_books()


@router.post("")
def post_book(data: CreateBook):
    """Create a new book with placeholder data."""
    if not create_book(data.id, data.model_dump()):
        raise HTTPException(status_code=409, detail="Book ID already exists")
    return {"ok": True, "id": data.id}


@router.get("/{book_id}")
def read_book(book_id: str):
    """Get a single book with chapter metadata."""
    book = get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.patch("/{book_id}")
def patch_book(book_id: str, data: UpdateBook):
    """Update book metadata (title, author, description)."""
    update_data = data.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    if not update_book(book_id, update_data):
        raise HTTPException(status_code=404, detail="Book not found")
    return {"ok": True}


@router.post("/{book_id}/cover")
async def upload_book_cover(book_id: str, file: UploadFile = File(...)):
    """Upload a new cover image for a book."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    url = upload_cover(book_id, contents, file.content_type)
    return {"ok": True, "cover": url}
