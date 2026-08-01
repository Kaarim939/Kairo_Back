from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional

ALLOWED_ANIMATIONS = [
    "shaking", "zoomOutSlow", "zoomOut", "impact",
    "fadeIn", "slideUp", "slideDown", "slideLeft", "slideRight",
]

ALLOWED_ALIGNS = ["left", "center", "right"]

ALLOWED_LANGUAGES = ["en", "fr", "es", "pt", "ar", "ko", "ja"]

UI_LANGUAGES = ["en", "fr", "es"]


# Multilingual string: {en: "...", fr: "...", es: "..."}
LocalizedStr = dict[str, str]


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
    # Webtoon gutter below this panel, as a percentage of column width.
    gapAfter: Optional[float] = Field(default=None, ge=0, le=200)
    # Extra quads that belong to this panel but sit outside its bounds, for art
    # that breaks the frame (a head, an arm, a sound effect).
    overflows: Optional[list[list[Point]]] = None

    @field_validator("points")
    @classmethod
    def validate_points(cls, v: list[Point] | None) -> list[Point] | None:
        if v is not None and len(v) != 4:
            raise ValueError("points must have exactly 4 entries")
        return v

    @field_validator("overflows")
    @classmethod
    def validate_overflows(
        cls, v: list[list[Point]] | None
    ) -> list[list[Point]] | None:
        if v is not None:
            for poly in v:
                if len(poly) < 3:
                    raise ValueError("each overflow needs at least 3 points")
                if len(poly) > 64:
                    raise ValueError("each overflow allows at most 64 points")
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
    coloredImageUrl: Optional[str] = Field(default=None, max_length=500)
    panels: list[Panel]
    width: Optional[float] = Field(default=None, gt=0)
    height: Optional[float] = Field(default=None, gt=0)
    ostId: Optional[str] = Field(default=None, max_length=100)


class Chapter(BaseModel):
    id: int
    number: float = Field(gt=0)
    name: LocalizedStr
    free: bool
    pageWidth: float = Field(gt=0)
    pageHeight: float = Field(gt=0)
    fontSize: float = Field(gt=0, le=200)
    font: str = Field(max_length=100)
    availableLanguages: list[str]
    hasColored: bool = False
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
    name: LocalizedStr
    free: bool
    pageWidth: float
    pageHeight: float
    fontSize: float
    font: str
    availableLanguages: list[str]
    hasColored: bool = False
    pageCount: int


class Volume(BaseModel):
    id: str = Field(max_length=100)
    number: float = Field(gt=0)
    name: LocalizedStr
    summary: LocalizedStr
    cover: str = Field(default="", max_length=500)
    chapters: list[int] = Field(default_factory=list)


class Character(BaseModel):
    id: str = Field(max_length=100)
    name: LocalizedStr
    description: LocalizedStr
    image: str = Field(default="", max_length=500)
    nickname: Optional[LocalizedStr] = None
    team: Optional[LocalizedStr] = None


class Book(BaseModel):
    id: str = Field(max_length=100, pattern=r'^[a-z0-9-]+$')
    title: LocalizedStr
    author: str = Field(max_length=200)
    description: LocalizedStr
    chapters: list[Chapter]
    volumes: Optional[list[Volume]] = None
    characters: Optional[list[Character]] = None


class BookSummary(BaseModel):
    """Book without full chapter data — for listing."""
    id: str
    title: LocalizedStr
    author: str
    description: LocalizedStr
    cover: str
    visible: bool = True
    order: int = 0
    chapters: list[ChapterMeta]
    volumes: Optional[list[Volume]] = None
    characters: Optional[list[Character]] = None


# --- Update models (partial, for optimized saves) ---

class UpdatePage(BaseModel):
    """Partial page update — only changed fields."""
    panels: Optional[list[Panel]] = None
    width: Optional[float] = Field(default=None, gt=0)
    height: Optional[float] = Field(default=None, gt=0)
    ostId: Optional[str] = Field(default=None, max_length=100)


class UpdateChapterMeta(BaseModel):
    """Update chapter metadata (not pages)."""
    number: Optional[float] = Field(default=None, gt=0)
    name: Optional[LocalizedStr] = None
    free: Optional[bool] = None
    pageWidth: Optional[float] = Field(default=None, gt=0)
    pageHeight: Optional[float] = Field(default=None, gt=0)
    fontSize: Optional[float] = Field(default=None, gt=0, le=200)
    font: Optional[str] = Field(default=None, max_length=100)
    availableLanguages: Optional[list[str]] = None
    hasColored: Optional[bool] = None

    @field_validator("availableLanguages")
    @classmethod
    def validate_languages(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for lang in v:
                if lang not in ALLOWED_LANGUAGES:
                    raise ValueError(f"language '{lang}' not in {ALLOWED_LANGUAGES}")
        return v


class CreateChapter(BaseModel):
    """Create a new empty chapter."""
    number: float = Field(gt=0)
    name: LocalizedStr
    free: bool = False


class CreateBook(BaseModel):
    """Create a new book with placeholder data."""
    id: str = Field(max_length=100, pattern=r'^[a-z0-9-]+$')
    title: LocalizedStr


class ReorderPages(BaseModel):
    pages: list[dict]


class UpdateBook(BaseModel):
    """Update book metadata."""
    title: Optional[LocalizedStr] = None
    author: Optional[str] = Field(default=None, max_length=200)
    description: Optional[LocalizedStr] = None
    visible: Optional[bool] = None
    order: Optional[int] = None
    volumes: Optional[list[Volume]] = None
    characters: Optional[list[Character]] = None


class OSTRecord(BaseModel):
    """A single OST (background music track) in the global library."""
    id: str
    name: str = Field(max_length=200)
    origin: str = Field(default="", max_length=200)
    tags: list[str] = Field(default_factory=list)
    duration: float = Field(ge=0, le=36000)
    url: str = Field(max_length=500)
    createdAt: Optional[str] = None


class CreateOSTMeta(BaseModel):
    """Form-fields portion of the multipart OST upload."""
    name: str = Field(max_length=200)
    origin: str = Field(default="", max_length=200)
    tags: list[str] = Field(default_factory=list)
    duration: float = Field(ge=0, le=36000)


class UpdateOSTMeta(BaseModel):
    """Partial update for OST metadata. The audio file is NOT replaceable here."""
    name: Optional[str] = Field(default=None, max_length=200)
    origin: Optional[str] = Field(default=None, max_length=200)
    tags: Optional[list[str]] = None
    duration: Optional[float] = Field(default=None, ge=0, le=36000)
