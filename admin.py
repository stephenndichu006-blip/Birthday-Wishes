"""
Admin functionality for the Birthday Website
Handles photo management, content administration, and backend operations.
"""

import copy
import json
import os
import shutil
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Dict, List, Any
import mimetypes

from server import ROOT, DATA_FILE, read_birthday_data, write_birthday_data, utc_now_iso

# Photo Management Constants
PHOTOS_DIR = ROOT / "assets" / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


# Photo Management Functions
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


def parse_multipart_data(headers: Dict[str, str], rfile, content_length: int) -> Dict[str, Any]:
    """Parse multipart form data"""
    content_type = headers.get('Content-Type', '')
    boundary = content_type.split('boundary=')[1] if 'boundary=' in content_type else None

    if not boundary:
        raise ValueError("No boundary found in Content-Type")

    if content_length <= 0:
        raise ValueError("Invalid content length")

    raw_body = rfile.read(content_length)
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

        headers_part = part[:header_end].decode('utf-8', errors='ignore')
        content = part[header_end + 4:-2]  # Remove \r\n at end

        # Extract field name and filename
        content_disposition = None
        for line in headers_part.split('\r\n'):
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


# Admin Request Handlers
class AdminHandlers:
    """Handles admin-related HTTP requests"""

    def __init__(self, handler_instance):
        self.handler = handler_instance

    def handle_photo_upload(self) -> None:
        """Handle photo upload"""
        content_type = self.handler.headers.get('Content-Type', '')

        if not content_type.startswith('multipart/form-data'):
            self.handler.respond_json({"error": "Content-Type must be multipart/form-data"}, HTTPStatus.BAD_REQUEST)
            return

        # Parse multipart form data
        try:
            form_data = parse_multipart_data(self.handler.headers, self.handler.rfile, self.handler.get_content_length())
            if 'photo' not in form_data:
                self.handler.respond_json({"error": "No photo file provided"}, HTTPStatus.BAD_REQUEST)
                return

            file_data = form_data['photo']
            filename = file_data['filename']
            content = file_data['content']

            saved_filename = save_uploaded_photo(content, filename)
            self.handler.respond_json({
                "message": "Photo uploaded successfully",
                "filename": saved_filename,
                "path": f"/assets/photos/{saved_filename}"
            })

        except Exception as e:
            self.handler.respond_json({"error": str(e)}, HTTPStatus.BAD_REQUEST)

    def handle_photo_replace(self) -> None:
        """Handle photo replacement"""
        content_type = self.handler.headers.get('Content-Type', '')

        if not content_type.startswith('multipart/form-data'):
            self.handler.respond_json({"error": "Content-Type must be multipart/form-data"}, HTTPStatus.BAD_REQUEST)
            return

        try:
            form_data = parse_multipart_data(self.handler.headers, self.handler.rfile, self.handler.get_content_length())
            if 'photo' not in form_data:
                self.handler.respond_json({"error": "No photo file provided"}, HTTPStatus.BAD_REQUEST)
                return

            old_filename = self.handler.headers.get('X-Replace-Filename', '')
            if not old_filename:
                self.handler.respond_json({"error": "X-Replace-Filename header required"}, HTTPStatus.BAD_REQUEST)
                return

            file_data = form_data['photo']
            new_filename = file_data['filename']
            content = file_data['content']

            saved_filename = replace_photo(old_filename, content, new_filename)
            self.handler.respond_json({
                "message": "Photo replaced successfully",
                "filename": saved_filename,
                "path": f"/assets/photos/{saved_filename}"
            })

        except Exception as e:
            self.handler.respond_json({"error": str(e)}, HTTPStatus.BAD_REQUEST)

    def handle_update_assignments(self) -> None:
        """Handle photo assignment updates"""
        content_length = self.handler.get_content_length()
        if content_length < 0:
            self.handler.respond_json({"error": "Content-Length header is required."}, HTTPStatus.LENGTH_REQUIRED)
            return

        raw_body = self.handler.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
            assignments = payload.get("assignments", {})
            updated = update_photo_assignments(assignments)
            self.handler.respond_json({"message": "Photo assignments updated", "assignments": updated})
        except json.JSONDecodeError:
            self.handler.respond_json({"error": "Invalid JSON payload."}, HTTPStatus.BAD_REQUEST)
        except Exception as e:
            self.handler.respond_json({"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_photo_delete(self, filename: str) -> None:
        """Handle photo deletion"""
        try:
            success = delete_photo(filename)
            if success:
                self.handler.respond_json({"message": f"Photo {filename} deleted successfully"})
            else:
                self.handler.respond_json({"error": f"Photo {filename} not found"}, HTTPStatus.NOT_FOUND)
        except Exception as e:
            self.handler.respond_json({"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)