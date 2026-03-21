from fastapi import APIRouter
from models.schemas import Book
from services.firebase import import_book_json

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/book")
def import_book(book_data: Book):
    """Import a full book JSON into Firebase.

    Validates the entire structure via Pydantic before saving.
    """
    book_id = import_book_json(book_data.model_dump())
    return {"ok": True, "bookId": book_id}
