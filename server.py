from __future__ import annotations

import copy
import json
import mimetypes
import os
import shutil
import socket
import sys
import tempfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "birthday_data.json"
MAX_BODY_BYTES = 4_096
MAX_HISTORY_ITEMS = 12
FIELD_LIMITS = {
    "name": 80,
    "day": 30,
    "date": 60,
}
DEFAULT_DATA = {
    "name": "Ann Wanjiku",
    "day": "Saturday",
    "date": "14 December 2026",
    "settings": {
        "autoplay_enabled": True,
        "slide_duration_seconds": 14,
        "music_mode": "local",
        "welcome_title": "Welcome to Ann Wanjiku's Birthday Experience",
        "welcome_subtitle": "Tap to begin the music, unlock the full celebration, and enjoy every page like a guided birthday story.",
        "finale_message": "Thank you for celebrating Ann Wanjiku with love, beauty, music, and unforgettable joy.",
    },
    "guest_wishes": [
        "May your year overflow with peace and answered prayers.",
        "May every room you walk into feel brighter because of your smile.",
        "May this new chapter bring bold wins, deep joy, and beautiful memories.",
    ],
    "favorite_things": [
        {"label": "Favorite Vibe", "value": "Soft glam and golden-hour confidence"},
        {"label": "Favorite Soundtrack", "value": "Warm birthday songs and joyful Afro-pop"},
        {"label": "Favorite Treat", "value": "Sweet cake, sweet words, and sweeter memories"},
        {"label": "Favorite Dream", "value": "A year filled with peace, growth, and glowing success"},
    ],
    "reasons_wall": [
        "She brings calm, grace, and warmth wherever she goes.",
        "Her laughter makes ordinary moments feel special.",
        "She deserves a celebration that feels personal, joyful, and beautiful.",
        "Her future is full of promise and deserves to be spoken over with love.",
    ],
    "milestones": [
        {"time": "Morning", "title": "Wake up celebrated", "detail": "The day starts with grateful prayers, smiles, and the first beautiful wishes."},
        {"time": "Afternoon", "title": "Gather the love", "detail": "Calls, messages, and laughter fill the day with warmth and attention."},
        {"time": "Evening", "title": "Dress up and shine", "detail": "Photos, cake, and glowing confidence turn the day into a full celebration."},
        {"time": "Night", "title": "End in gratitude", "detail": "The last moments become a memory to carry into the new year ahead."},
    ],
    "memory_slides": [
        {"title": "The first smile of the day", "caption": "A birthday morning that begins with beauty, peace, and anticipation.", "image": "/assets/photos/photo-1.jpeg"},
        {"title": "Moments worth saving", "caption": "Sweet photos and sweet words turn the celebration into memory.", "image": "/assets/photos/photo-2.jpeg"},
        {"title": "A queen in her glow", "caption": "Confidence, joy, and grace deserve to be remembered in full color.", "image": "/assets/photos/photo-3.jpeg"},
    ],
}
APP_MANIFEST = {
    "id": "/home.html",
    "name": "Birthday Wishes",
    "short_name": "Birthday",
    "description": "A beautiful birthday website that can be installed on a phone like an app.",
    "start_url": "/home.html",
    "scope": "/",
    "display": "standalone",
    "background_color": "#fff8ef",
    "theme_color": "#9f2d56",
    "orientation": "portrait",
    "icons": [
        {
            "src": "/assets/app-icon-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any maskable",
        },
        {
            "src": "/assets/app-icon-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any maskable",
        },
        {
            "src": "/assets/birthday-bloom.svg",
            "sizes": "any",
            "type": "image/svg+xml",
            "purpose": "any maskable",
        }
    ],
}
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


def ensure_data_file() -> None:
    if not DATA_FILE.exists():
        write_json_file(build_storage_record(DEFAULT_DATA, []))


def write_json_file(payload: dict[str, object]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=DATA_FILE.parent,
        delete=False,
    ) as temp_file:
        json.dump(payload, temp_file, indent=2)
        temp_path = Path(temp_file.name)

    temp_path.replace(DATA_FILE)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def get_local_ip() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def get_server_host() -> str:
    return os.environ.get("HOST", DEFAULT_HOST)


def get_server_port() -> int:
    raw_port = os.environ.get("PORT", str(DEFAULT_PORT))
    try:
        return int(raw_port)
    except ValueError:
        return DEFAULT_PORT


def build_storage_record(
    birthday: dict[str, object],
    history: list[dict[str, object]] | None = None,
    updated_at: str | None = None,
    save_count: int = 0,
) -> dict[str, object]:
    return {
        "name": birthday["name"],
        "day": birthday["day"],
        "date": birthday["date"],
        "updated_at": updated_at or utc_now_iso(),
        "save_count": save_count,
        "history": history or [],
        "settings": copy.deepcopy(birthday.get("settings", DEFAULT_DATA["settings"])),
        "guest_wishes": copy.deepcopy(birthday.get("guest_wishes", DEFAULT_DATA["guest_wishes"])),
        "favorite_things": copy.deepcopy(birthday.get("favorite_things", DEFAULT_DATA["favorite_things"])),
        "reasons_wall": copy.deepcopy(birthday.get("reasons_wall", DEFAULT_DATA["reasons_wall"])),
        "milestones": copy.deepcopy(birthday.get("milestones", DEFAULT_DATA["milestones"])),
        "memory_slides": copy.deepcopy(birthday.get("memory_slides", DEFAULT_DATA["memory_slides"])),
    }


def read_storage_record() -> dict[str, object]:
    ensure_data_file()
    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        data = build_storage_record(DEFAULT_DATA, [])
        write_json_file(data)

    if not isinstance(data, dict):
        data = {}

    # Support older flat JSON files and normalize them into the richer shape.
    birthday = {
        "name": str(data.get("name", DEFAULT_DATA["name"])).strip() or DEFAULT_DATA["name"],
        "day": str(data.get("day", DEFAULT_DATA["day"])).strip() or DEFAULT_DATA["day"],
        "date": str(data.get("date", DEFAULT_DATA["date"])).strip() or DEFAULT_DATA["date"],
    }
    history = data.get("history", [])
    normalized_history = history if isinstance(history, list) else []
    updated_at = str(data.get("updated_at", utc_now_iso()))
    save_count = data.get("save_count", 0)
    if not isinstance(save_count, int):
        save_count = 0

    settings = data.get("settings", DEFAULT_DATA["settings"])
    guest_wishes = data.get("guest_wishes", DEFAULT_DATA["guest_wishes"])
    favorite_things = data.get("favorite_things", DEFAULT_DATA["favorite_things"])
    reasons_wall = data.get("reasons_wall", DEFAULT_DATA["reasons_wall"])
    milestones = data.get("milestones", DEFAULT_DATA["milestones"])
    memory_slides = data.get("memory_slides", DEFAULT_DATA["memory_slides"])
    birthday.update(
        {
            "settings": normalize_settings(settings),
            "guest_wishes": normalize_string_list(guest_wishes, DEFAULT_DATA["guest_wishes"]),
            "favorite_things": normalize_labeled_items(favorite_things, DEFAULT_DATA["favorite_things"]),
            "reasons_wall": normalize_string_list(reasons_wall, DEFAULT_DATA["reasons_wall"]),
            "milestones": normalize_milestones(milestones, DEFAULT_DATA["milestones"]),
            "memory_slides": normalize_memory_slides(memory_slides, DEFAULT_DATA["memory_slides"]),
        }
    )

    normalized = build_storage_record(
        birthday,
        normalized_history[:MAX_HISTORY_ITEMS],
        updated_at=updated_at,
        save_count=max(save_count, 0),
    )
    return normalized


def read_birthday_data() -> dict[str, object]:
    data = read_storage_record()

    return {
        "name": str(data["name"]),
        "day": str(data["day"]),
        "date": str(data["date"]),
        "updated_at": str(data["updated_at"]),
        "save_count": int(data["save_count"]),
        "settings": copy.deepcopy(data["settings"]),
        "guest_wishes": copy.deepcopy(data["guest_wishes"]),
        "favorite_things": copy.deepcopy(data["favorite_things"]),
        "reasons_wall": copy.deepcopy(data["reasons_wall"]),
        "milestones": copy.deepcopy(data["milestones"]),
        "memory_slides": copy.deepcopy(data["memory_slides"]),
    }


def write_birthday_data(payload: dict[str, object]) -> dict[str, object]:
    previous = read_storage_record()
    history_entry = {
        "name": previous["name"],
        "day": previous["day"],
        "date": previous["date"],
        "replaced_at": utc_now_iso(),
    }
    history = [history_entry, *list(previous.get("history", []))]
    record = build_storage_record(
        payload,
        history[:MAX_HISTORY_ITEMS],
        updated_at=utc_now_iso(),
        save_count=int(previous.get("save_count", 0)) + 1,
    )
    write_json_file(record)
    return read_birthday_data()


def reset_birthday_data() -> dict[str, object]:
    previous = read_storage_record()
    history_entry = {
        "name": previous["name"],
        "day": previous["day"],
        "date": previous["date"],
        "replaced_at": utc_now_iso(),
        "action": "reset",
    }
    history = [history_entry, *list(previous.get("history", []))]
    record = build_storage_record(
        DEFAULT_DATA,
        history[:MAX_HISTORY_ITEMS],
        updated_at=utc_now_iso(),
        save_count=int(previous.get("save_count", 0)) + 1,
    )
    write_json_file(record)
    return read_birthday_data()


def read_birthday_history() -> dict[str, object]:
    data = read_storage_record()
    history = data.get("history", [])
    return {
        "history": history if isinstance(history, list) else [],
    }


def validate_birthday_payload(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object.")

    cleaned: dict[str, str] = {}
    for field_name in ("name", "day", "date"):
        value = str(payload.get(field_name, "")).strip()
        if not value:
            raise ValueError("Birthday name, day, and date are all required.")
        if len(value) > FIELD_LIMITS[field_name]:
            raise ValueError(
                f"{field_name.capitalize()} must be {FIELD_LIMITS[field_name]} characters or fewer."
            )
        cleaned[field_name] = value

    return cleaned


def normalize_string_list(value: object, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return copy.deepcopy(default)

    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned[:8] or copy.deepcopy(default)


def normalize_labeled_items(value: object, default: list[dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return copy.deepcopy(default)

    cleaned: list[dict[str, str]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        content = str(item.get("value", "")).strip()
        if label and content:
            cleaned.append({"label": label[:40], "value": content[:120]})

    return cleaned or copy.deepcopy(default)


def normalize_milestones(value: object, default: list[dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return copy.deepcopy(default)

    cleaned: list[dict[str, str]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        time = str(item.get("time", "")).strip()
        title = str(item.get("title", "")).strip()
        detail = str(item.get("detail", "")).strip()
        if time and title and detail:
            cleaned.append({"time": time[:30], "title": title[:60], "detail": detail[:180]})

    return cleaned or copy.deepcopy(default)


def normalize_memory_slides(value: object, default: list[dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return copy.deepcopy(default)

    cleaned: list[dict[str, str]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        caption = str(item.get("caption", "")).strip()
        image = str(item.get("image", "")).strip()
        if title and caption and image:
            cleaned.append({"title": title[:60], "caption": caption[:180], "image": image})

    return cleaned or copy.deepcopy(default)


def normalize_settings(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return copy.deepcopy(DEFAULT_DATA["settings"])

    autoplay_enabled = bool(value.get("autoplay_enabled", DEFAULT_DATA["settings"]["autoplay_enabled"]))
    music_mode = str(value.get("music_mode", DEFAULT_DATA["settings"]["music_mode"])).strip() or "local"
    slide_duration_seconds = value.get("slide_duration_seconds", DEFAULT_DATA["settings"]["slide_duration_seconds"])
    try:
        slide_duration_seconds = int(slide_duration_seconds)
    except (TypeError, ValueError):
        slide_duration_seconds = DEFAULT_DATA["settings"]["slide_duration_seconds"]
    slide_duration_seconds = min(25, max(8, slide_duration_seconds))

    return {
        "autoplay_enabled": autoplay_enabled,
        "slide_duration_seconds": slide_duration_seconds,
        "music_mode": music_mode[:20],
        "welcome_title": str(value.get("welcome_title", DEFAULT_DATA["settings"]["welcome_title"])).strip()[:90] or DEFAULT_DATA["settings"]["welcome_title"],
        "welcome_subtitle": str(value.get("welcome_subtitle", DEFAULT_DATA["settings"]["welcome_subtitle"])).strip()[:220] or DEFAULT_DATA["settings"]["welcome_subtitle"],
        "finale_message": str(value.get("finale_message", DEFAULT_DATA["settings"]["finale_message"])).strip()[:240] or DEFAULT_DATA["settings"]["finale_message"],
    }


def validate_extended_payload(payload: object) -> dict[str, object]:
    cleaned = validate_birthday_payload(payload)
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object.")

    cleaned["settings"] = normalize_settings(payload.get("settings", DEFAULT_DATA["settings"]))
    cleaned["guest_wishes"] = normalize_string_list(payload.get("guest_wishes", DEFAULT_DATA["guest_wishes"]), DEFAULT_DATA["guest_wishes"])
    cleaned["favorite_things"] = normalize_labeled_items(payload.get("favorite_things", DEFAULT_DATA["favorite_things"]), DEFAULT_DATA["favorite_things"])
    cleaned["reasons_wall"] = normalize_string_list(payload.get("reasons_wall", DEFAULT_DATA["reasons_wall"]), DEFAULT_DATA["reasons_wall"])
    cleaned["milestones"] = normalize_milestones(payload.get("milestones", DEFAULT_DATA["milestones"]), DEFAULT_DATA["milestones"])
    cleaned["memory_slides"] = normalize_memory_slides(payload.get("memory_slides", DEFAULT_DATA["memory_slides"]), DEFAULT_DATA["memory_slides"])
    return cleaned


# Photo Management Functions
PHOTOS_DIR = ROOT / "assets" / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def get_photo_assignments() -> Dict[str, str]:
    """Get current photo assignments from birthday data"""
    data = read_birthday_data()
    assignments = {}

    # Extract photo assignments from memory slides
    for slide in data.get("memory_slides", []):
        if "image" in slide and slide["image"]:
            assignments[slide["image"]] = f"memory_slide_{slide.get('title', 'unknown')}"

    # Add default assignments for known photos
    default_assignments = {
        "/assets/photos/photo-1.jpeg": "welcome_hero",
        "/assets/photos/photo-2.jpeg": "gallery_portrait",
        "/assets/photos/photo-3.jpeg": "birthday_intro"
    }

    for photo, location in default_assignments.items():
        if photo not in assignments:
            assignments[photo] = location

    return assignments

def list_photos() -> List[Dict[str, Any]]:
    """List all photos with their metadata"""
    photos = []
    assignments = get_photo_assignments()

    for photo_path in PHOTOS_DIR.glob("*"):
        if photo_path.suffix.lower() in ALLOWED_EXTENSIONS:
            stat = photo_path.stat()
            photos.append({
                "filename": photo_path.name,
                "path": f"/assets/photos/{photo_path.name}",
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "assignment": assignments.get(f"/assets/photos/{photo_path.name}", "unassigned")
            })

    return sorted(photos, key=lambda x: x["filename"])

def save_uploaded_photo(content: bytes, filename: str) -> str:
    """Save uploaded photo and return the filename"""
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("File too large. Maximum size is 10MB.")

    # Validate file type
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type or not mime_type.startswith('image/'):
        raise ValueError("Invalid file type. Only image files are allowed.")

    # Generate unique filename if it exists
    file_path = PHOTOS_DIR / filename
    counter = 1
    name, ext = file_path.stem, file_path.suffix
    while file_path.exists():
        file_path = PHOTOS_DIR / f"{name}_{counter}{ext}"
        counter += 1

    # Save the file
    with open(file_path, 'wb') as f:
        f.write(content)

    return file_path.name

def replace_photo(old_filename: str, new_content: bytes, new_filename: str) -> str:
    """Replace an existing photo with new content"""
    old_path = PHOTOS_DIR / old_filename
    if not old_path.exists():
        raise ValueError(f"Photo {old_filename} does not exist.")

    if len(new_content) > MAX_FILE_SIZE:
        raise ValueError("File too large. Maximum size is 10MB.")

    # Validate file type
    mime_type, _ = mimetypes.guess_type(new_filename)
    if not mime_type or not mime_type.startswith('image/'):
        raise ValueError("Invalid file type. Only image files are allowed.")

    # Backup old file
    backup_path = old_path.with_suffix(f"{old_path.suffix}.backup")
    shutil.copy2(old_path, backup_path)

    try:
        # Replace the file
        with open(old_path, 'wb') as f:
            f.write(new_content)
        return old_filename
    except Exception as e:
        # Restore backup on error
        shutil.copy2(backup_path, old_path)
        raise e

def delete_photo(filename: str) -> bool:
    """Delete a photo file"""
    file_path = PHOTOS_DIR / filename
    if file_path.exists():
        # Create backup before deletion
        backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
        shutil.copy2(file_path, backup_path)
        file_path.unlink()
        return True
    return False

def update_photo_assignments(assignments: Dict[str, str]) -> Dict[str, str]:
    """Update photo assignments in birthday data"""
    data = read_birthday_data()

    # Update memory slides with new assignments
    for slide in data.get("memory_slides", []):
        image_path = slide.get("image", "")
        if image_path in assignments:
            slide["image"] = assignments[image_path]

    write_birthday_data(data)
    return assignments


class BirthdayRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        path = self.get_request_path()

        # Handle API routes first
        if path.startswith("/api/"):
            if path == "/api/health":
                self.respond_json({"status": "ok"})
                return

            if path == "/api/birthday":
                self.respond_json(read_birthday_data())
                return

            if path == "/api/birthday/history":
                self.respond_json(read_birthday_history())
                return

            if path == "/api/photos":
                self.respond_json(list_photos())
                return

            if path == "/api/photos/assignments":
                self.respond_json(get_photo_assignments())
                return

            # If it's an API route but not recognized, return 404
            self.send_error(HTTPStatus.NOT_FOUND, "API endpoint not found.")
            return

        if path in {"/", "/index.html"}:
            self.path = "/home.html"

        if path == "/admin":
            self.path = "/admin.html"

        if path == "/manifest.webmanifest":
            self.respond_manifest(APP_MANIFEST)
            return

        super().do_GET()

    def do_POST(self) -> None:
        path = self.get_request_path()
        if path == "/api/birthday/reset":
            self.respond_json(reset_birthday_data())
            return

        if path == "/api/photos/upload":
            self.handle_photo_upload()
            return

        if path == "/api/photos/replace":
            self.handle_photo_replace()
            return

        if path.startswith("/api/photos/assignments") and path != "/api/photos/assignments":
            # Handle specific assignment updates
            pass
        elif path == "/api/photos/assignments":
            self.handle_update_assignments()
            return

        if path != "/api/birthday":
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found.")
            return

        content_length = self.get_content_length()
        if content_length < 0:
            self.respond_json({"error": "Content-Length header is required."}, HTTPStatus.LENGTH_REQUIRED)
            return
        if content_length > MAX_BODY_BYTES:
            self.respond_json({"error": "Payload is too large."}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return

        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except UnicodeDecodeError:
            self.respond_json({"error": "Request body must be UTF-8 encoded."}, HTTPStatus.BAD_REQUEST)
            return
        except json.JSONDecodeError:
            self.respond_json({"error": "Invalid JSON payload."}, HTTPStatus.BAD_REQUEST)
            return

        try:
            cleaned = validate_extended_payload(payload)
        except ValueError as error:
            self.respond_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return

        saved = write_birthday_data(cleaned)
        self.respond_json(saved)

    def do_PUT(self) -> None:
        self.do_POST()

    def do_DELETE(self) -> None:
        path = self.get_request_path()
        if path.startswith("/api/photos/"):
            filename = path.replace("/api/photos/", "")
            try:
                success = delete_photo(filename)
                if success:
                    self.respond_json({"message": f"Photo {filename} deleted successfully"})
                else:
                    self.respond_json({"error": f"Photo {filename} not found"}, HTTPStatus.NOT_FOUND)
            except Exception as e:
                self.respond_json({"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found.")

    def handle_photo_upload(self) -> None:
        """Handle photo upload"""
        content_type = self.headers.get('Content-Type', '')

        if not content_type.startswith('multipart/form-data'):
            self.respond_json({"error": "Content-Type must be multipart/form-data"}, HTTPStatus.BAD_REQUEST)
            return

        # Parse multipart form data
        try:
            form_data = self.parse_multipart_data()
            if 'photo' not in form_data:
                self.respond_json({"error": "No photo file provided"}, HTTPStatus.BAD_REQUEST)
                return

            file_data = form_data['photo']
            filename = file_data['filename']
            content = file_data['content']

            saved_filename = save_uploaded_photo(content, filename)
            self.respond_json({
                "message": "Photo uploaded successfully",
                "filename": saved_filename,
                "path": f"/assets/photos/{saved_filename}"
            })

        except Exception as e:
            self.respond_json({"error": str(e)}, HTTPStatus.BAD_REQUEST)

    def handle_photo_replace(self) -> None:
        """Handle photo replacement"""
        content_type = self.headers.get('Content-Type', '')

        if not content_type.startswith('multipart/form-data'):
            self.respond_json({"error": "Content-Type must be multipart/form-data"}, HTTPStatus.BAD_REQUEST)
            return

        try:
            form_data = self.parse_multipart_data()
            if 'photo' not in form_data:
                self.respond_json({"error": "No photo file provided"}, HTTPStatus.BAD_REQUEST)
                return

            old_filename = self.headers.get('X-Replace-Filename', '')
            if not old_filename:
                self.respond_json({"error": "X-Replace-Filename header required"}, HTTPStatus.BAD_REQUEST)
                return

            file_data = form_data['photo']
            new_filename = file_data['filename']
            content = file_data['content']

            saved_filename = replace_photo(old_filename, content, new_filename)
            self.respond_json({
                "message": "Photo replaced successfully",
                "filename": saved_filename,
                "path": f"/assets/photos/{saved_filename}"
            })

        except Exception as e:
            self.respond_json({"error": str(e)}, HTTPStatus.BAD_REQUEST)

    def handle_update_assignments(self) -> None:
        """Handle photo assignment updates"""
        content_length = self.get_content_length()
        if content_length < 0:
            self.respond_json({"error": "Content-Length header is required."}, HTTPStatus.LENGTH_REQUIRED)
            return

        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
            assignments = payload.get("assignments", {})
            updated = update_photo_assignments(assignments)
            self.respond_json({"message": "Photo assignments updated", "assignments": updated})
        except json.JSONDecodeError:
            self.respond_json({"error": "Invalid JSON payload."}, HTTPStatus.BAD_REQUEST)
        except Exception as e:
            self.respond_json({"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def parse_multipart_data(self) -> Dict[str, Any]:
        """Parse multipart form data"""
        content_type = self.headers.get('Content-Type', '')
        boundary = content_type.split('boundary=')[1] if 'boundary=' in content_type else None

        if not boundary:
            raise ValueError("No boundary found in Content-Type")

        content_length = self.get_content_length()
        if content_length <= 0:
            raise ValueError("Invalid content length")

        raw_body = self.rfile.read(content_length)
        boundary_bytes = f'--{boundary}'.encode()

        parts = raw_body.split(boundary_bytes)
        form_data = {}

        for part in parts:
            if not part or part == b'--\r\n' or part == b'--':
                continue

            # Parse headers and content
            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                continue

            headers = part[:header_end].decode('utf-8', errors='ignore')
            content = part[header_end + 4:-2]  # Remove \r\n at end

            # Extract field name and filename
            content_disposition = None
            for line in headers.split('\r\n'):
                if line.lower().startswith('content-disposition:'):
                    content_disposition = line
                    break

            if not content_disposition:
                continue

            # Parse field name and filename
            field_name = None
            filename = None
            for param in content_disposition.split(';'):
                param = param.strip()
                if param.startswith('name="'):
                    field_name = param[6:-1]
                elif param.startswith('filename="'):
                    filename = param[10:-1]

            if field_name:
                form_data[field_name] = {
                    'filename': filename or f'upload_{len(form_data)}',
                    'content': content
                }

        return form_data

    def respond_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def respond_manifest(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def get_request_path(self) -> str:
        return urlparse(self.path).path

    def get_content_length(self) -> int:
        raw_value = self.headers.get("Content-Length")
        if raw_value is None:
            return -1

        try:
            return int(raw_value)
        except ValueError:
            return -1

    def log_message(self, format: str, *args) -> None:
        super().log_message("[%s] " + format, self.log_date_time_string(), *args)


def run() -> None:
    ensure_data_file()
    host = get_server_host()
    port = get_server_port()
    server = ThreadingHTTPServer((host, port), BirthdayRequestHandler)
    local_ip = get_local_ip()
    print(f"Birthday site running at http://127.0.0.1:{port}")
    if host == "0.0.0.0":
        print(f"Phone install link on the same Wi-Fi: http://{local_ip}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
