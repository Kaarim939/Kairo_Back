"""Authors CRUD endpoints.

Writes are gated by the global AuthMiddleware (admin only); reads are public,
since the author page is part of the public site.
"""
from fastapi import APIRouter, HTTPException
from models.schemas import Author, CreateAuthor, UpdateAuthor
from services.authors import (
    list_authors,
    get_author,
    create_author,
    update_author,
    delete_author,
)

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("")
def list_all_authors() -> list[Author]:
    """Public read of every author."""
    return list_authors()


@router.get("/{author_id}")
def read_author(author_id: str) -> Author:
    author = get_author(author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    return author


@router.post("")
def add_author(data: CreateAuthor):
    author = create_author(data.id, data.name)
    if author is None:
        raise HTTPException(status_code=409, detail="Author id already exists")
    return author


@router.patch("/{author_id}")
def patch_author(author_id: str, data: UpdateAuthor):
    update_data = data.model_dump(exclude_none=True)
    if not update_data:
        return {"ok": True}
    if "links" in update_data:
        update_data["links"] = [
            link if isinstance(link, dict) else link.model_dump()
            for link in update_data["links"]
        ]
    if not update_author(author_id, update_data):
        raise HTTPException(status_code=404, detail="Author not found")
    return {"ok": True}


@router.delete("/{author_id}")
def remove_author(author_id: str):
    if not delete_author(author_id):
        raise HTTPException(status_code=404, detail="Author not found")
    return {"ok": True}
