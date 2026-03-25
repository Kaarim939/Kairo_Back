from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional

ALLOWED_ANIMATIONS = [
    "shaking", "zoomOutSlow", "zoomOut", "impact",
    "fadeIn", "slideUp", "slideDown", "slideLeft", "slideRight",
]

ALLOWED_ALIGNS = ["left", "center", "right"]

ALLOWED_LANGUAGES = ["en", "fr", "es", "ja"]


class TextLangEntry(BaseModel):
    text: str = Field(max_length=2000)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    specificSize: Optional[float] = Field(default=None, gt=0, le=200)


class PanelText(BaseModel):
    id: str = Field(max_length=100)
    textLang: dict[str, TextLangEntry]
    align: Optional[str] = None
    lineHeight: Optional[float] = Field(default=None, ge=0, le=100)
    specificFont: Optional[str] = Field(default=None, max_length=100)
    color: Optional[str] = Field(default=None, max_length=20)
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    stroke: Optional[bool] = None
    strokeSize: Optional[float] = Field(default=None, ge=0, le=50)
    strokeColor: Optional[str] = Field(default=None, max_length=20)

    @field_validator("align")
    @classmethod
    def validate_align(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_ALIGNS:
            raise ValueError(f"align must be one of {ALLOWED_ALIGNS}")
        return v


class Point(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class Panel(BaseModel):
    id: str = Field(max_length=100)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    points: Optional[list[Point]] = None
    texts: Optional[list[PanelText]] = None
    animation: Optional[str] = None

    @field_validator("points")
    @classmethod
    def validate_points(cls, v: list[Point] | None) -> list[Point] | None:
        if v is not None and len(v) != 4:
            raise ValueError("points must have exactly 4 entries")
        return v

    @field_validator("animation")
    @classmethod
    def validate_animation(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_ANIMATIONS:
            raise ValueError(f"animation must be one of {ALLOWED_ANIMATIONS}")
        return v


class Page(BaseModel):
    id: str = Field(max_length=100)
    pageNumber: int = Field(gt=0)
    imageUrl: str = Field(max_length=500)
    panels: list[Panel]
    width: Optional[float] = Field(default=None, gt=0)
    height: Optional[float] = Field(default=None, gt=0)


class Chapter(BaseModel):
    id: int
    number: float = Field(gt=0)
    name: str = Field(max_length=200)
    free: bool
    pageWidth: float = Field(gt=0)
    pageHeight: float = Field(gt=0)
    fontSize: float = Field(gt=0, le=200)
    font: str = Field(max_length=100)
    availableLanguages: list[str]
    pages: list[Page]

    @field_validator("availableLanguages")
    @classmethod
    def validate_languages(cls, v: list[str]) -> list[str]:
        for lang in v:
            if lang not in ALLOWED_LANGUAGES:
                raise ValueError(f"language '{lang}' not in {ALLOWED_LANGUAGES}")
        return v


class ChapterMeta(BaseModel):
    """Chapter without pages — for book listing."""
    id: int
    number: float
    name: str
    free: bool
    pageWidth: float
    pageHeight: float
    fontSize: float
    font: str
    availableLanguages: list[str]
    pageCount: int


class Book(BaseModel):
    id: str = Field(max_length=100, pattern=r'^[a-z0-9-]+$')
    title: str = Field(max_length=200)
    author: str = Field(max_length=200)
    description: str = Field(max_length=5000)
    chapters: list[Chapter]


class BookSummary(BaseModel):
    """Book without full chapter data — for listing."""
    id: str
    title: str
    author: str
    description: str
    cover: str
    chapters: list[ChapterMeta]


# --- Update models (partial, for optimized saves) ---

class UpdatePage(BaseModel):
    """Partial page update — only changed fields."""
    panels: Optional[list[Panel]] = None
    width: Optional[float] = Field(default=None, gt=0)
    height: Optional[float] = Field(default=None, gt=0)


class UpdateChapterMeta(BaseModel):
    """Update chapter metadata (not pages)."""
    number: Optional[float] = Field(default=None, gt=0)
    name: Optional[str] = Field(default=None, max_length=200)
    free: Optional[bool] = None
    pageWidth: Optional[float] = Field(default=None, gt=0)
    pageHeight: Optional[float] = Field(default=None, gt=0)
    fontSize: Optional[float] = Field(default=None, gt=0, le=200)
    font: Optional[str] = Field(default=None, max_length=100)
    availableLanguages: Optional[list[str]] = None

    @field_validator("availableLanguages")
    @classmethod
    def validate_languages(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for lang in v:
                if lang not in ALLOWED_LANGUAGES:
                    raise ValueError(f"language '{lang}' not in {ALLOWED_LANGUAGES}")
        return v


class UpdateBook(BaseModel):
    """Update book metadata."""
    title: Optional[str] = Field(default=None, max_length=200)
    author: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
