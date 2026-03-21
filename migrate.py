"""
Migration script: uploads all front-end data to Firebase.
- Books & chapters metadata → Firestore
- Pages with panels/texts → Firestore
- Images → Firebase Storage

Run from /back:
    python migrate.py

Requires:
    - kairo-firebase-credentials.json in /back
    - FIREBASE_STORAGE_BUCKET in .env (e.g. kairo-reader.appspot.com)
"""

import json
import os
import sys
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv

load_dotenv()

# --- Init Firebase ---
cred_path = os.getenv("FIREBASE_CREDENTIALS", "kairo-firebase-credentials.json")
cred = credentials.Certificate(cred_path)
bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "kairo-reader.firebasestorage.app")
print(f"Using bucket: {bucket_name}")
# Delete any existing app to avoid conflicts with uvicorn's init
try:
    firebase_admin.delete_app(firebase_admin.get_app())
except ValueError:
    pass
firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
db = firestore.client()
bucket = storage.bucket()

# --- Paths ---
FRONT_ROOT = Path(__file__).parent.parent
ASSETS = FRONT_ROOT / "src" / "assets"
PUBLIC = FRONT_ROOT / "public"

# --- Book definitions (matching books.ts) ---
BOOKS = [
    {
        "id": "naruto",
        "title": "Naruto",
        "author": "Masashi Kishimoto",
        "description": "Naruto Uzumaki, a young ninja shunned by his village for harboring a fearsome nine-tailed fox spirit, dreams of becoming the Hokage — the strongest ninja and leader of the village.",
        "chapters": [
            {
                "id": 1,
                "title": "Chapter 1 — Uzumaki Naruto",
                "free": True,
                "pageWidth": 1080,
                "pageHeight": 1620,
                "fontSize": 16,
                "font": "CCWildWords",
                "availableLanguages": ["en", "fr"],
                "pagesJson": ASSETS / "naruto" / "chap1" / "pages.json",
                "imagesDir": PUBLIC / "Mangas" / "Naruto" / "Chap1",
            }
        ],
    },
    {
        "id": "som-de-fundo",
        "title": "Som de Fundo",
        "author": "Unknown",
        "description": "A story set in the world of football, exploring the passion, pressure, and dreams of young players chasing glory.",
        "chapters": [
            {
                "id": 1,
                "title": "Chapter 1",
                "free": True,
                "pageWidth": 1464,
                "pageHeight": 2272,
                "fontSize": 37,
                "font": "CCWildWords",
                "availableLanguages": ["en", "fr", "es"],
                "pagesJson": ASSETS / "sumdefundo" / "chap1" / "pages.json",
                "imagesDir": PUBLIC / "Mangas" / "SomDeFundo",
            }
        ],
    },
    {
        "id": "one-piece",
        "title": "One Piece",
        "author": "Eiichiro Oda",
        "description": "Monkey D. Luffy sets off on a grand adventure to find the legendary treasure One Piece and become the King of the Pirates.",
        "chapters": [
            {
                "id": 1155,
                "title": "Chapter 1155",
                "free": True,
                "pageWidth": 1403,
                "pageHeight": 2048,
                "fontSize": 16,
                "font": "CCWildWords",
                "availableLanguages": ["fr"],
                "pagesJson": ASSETS / "onepiece" / "chap1155" / "pages.json",
                "imagesDir": PUBLIC / "Mangas" / "One Piece" / "chap1155",
            }
        ],
    },
]


def upload_image(local_path: Path, storage_path: str) -> str:
    """Upload an image to Firebase Storage and return its public URL."""
    blob = bucket.blob(storage_path)
    if blob.exists():
        print(f"  [skip] {storage_path} already exists")
    else:
        blob.upload_from_filename(str(local_path), content_type="image/png" if local_path.suffix.lower() == ".png" else "image/jpeg")
        print(f"  [upload] {storage_path}")
    blob.make_public()
    return blob.public_url


def get_image_filename(image_url: str) -> str:
    """Extract filename from imageUrl like '/Mangas/Naruto/Chap1/1.jpg' → '1.jpg'"""
    return image_url.split("/")[-1]


def migrate():
    print("Starting migration...\n")

    for book_def in BOOKS:
        book_id = book_def["id"]
        print(f"=== Book: {book_def['title']} ({book_id}) ===")

        # Write book metadata
        book_meta = {
            "title": book_def["title"],
            "author": book_def["author"],
            "description": book_def["description"],
        }
        db.collection("books").document(book_id).set(book_meta)
        print(f"  [firestore] books/{book_id}")

        for ch_def in book_def["chapters"]:
            ch_id = str(ch_def["id"])
            print(f"\n  --- Chapter {ch_id}: {ch_def['title']} ---")

            # Write chapter metadata
            ch_meta = {
                "title": ch_def["title"],
                "free": ch_def["free"],
                "pageWidth": ch_def["pageWidth"],
                "pageHeight": ch_def["pageHeight"],
                "fontSize": ch_def["fontSize"],
                "font": ch_def["font"],
                "availableLanguages": ch_def["availableLanguages"],
            }
            ch_ref = db.collection("books").document(book_id).collection("chapters").document(ch_id)
            ch_ref.set(ch_meta)
            print(f"  [firestore] books/{book_id}/chapters/{ch_id}")

            # Load pages JSON
            pages_json_path = ch_def["pagesJson"]
            if not pages_json_path.exists():
                print(f"  [error] Pages JSON not found: {pages_json_path}")
                continue

            pages = json.loads(pages_json_path.read_text(encoding="utf-8"))
            images_dir = ch_def["imagesDir"]

            for page in pages:
                page_id = page["id"]
                image_filename = get_image_filename(page["imageUrl"])
                local_image = images_dir / image_filename

                # Upload image to Storage
                storage_path = f"mangas/{book_id}/{ch_id}/{image_filename}"
                if local_image.exists():
                    public_url = upload_image(local_image, storage_path)
                    page["imageUrl"] = public_url
                else:
                    print(f"  [warn] Image not found: {local_image}")

                # Write page to Firestore
                page_data = {k: v for k, v in page.items() if k != "id"}
                ch_ref.collection("pages").document(page_id).set(page_data)

            print(f"  [firestore] {len(pages)} pages uploaded")

    print("\n✓ Migration complete!")


if __name__ == "__main__":
    migrate()
