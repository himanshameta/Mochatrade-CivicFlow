"""
CivicFlow — Vault Storage Utilities
======================================
Local filesystem operations for the document vault.
All files are stored locally only — no third-party storage.

Storage layout:
  uploads/user_docs/{user_id}/{category}/{timestamp}__{safe_name}.{ext}
  uploads/temp_sessions/{session_id}/{field_name}.{ext}
"""
import mimetypes
import os
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional


# ---------------------------------------------------------------------------
# Blocked extensions (security)
# ---------------------------------------------------------------------------
BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".com", ".msi", ".scr",
    ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".pif", ".reg", ".dll", ".sys",
}

# ---------------------------------------------------------------------------
# Filename sanitization
# ---------------------------------------------------------------------------

def sanitize_filename(name: str, max_length: int = 200) -> str:
    """
    Produce a safe filename from an arbitrary user string.

    Rules:
      - Normalize unicode to ASCII-safe form
      - Strip path separators, null bytes, control characters
      - Replace spaces/special chars with hyphens
      - Collapse repeated hyphens
      - Limit total length
      - Fallback to 'document' if result is empty
    """
    if not name:
        return "document"

    # Normalize unicode
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")

    # Strip path components (prevent traversal)
    name = os.path.basename(name)

    # Remove control chars and null bytes
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)

    # Replace problematic characters with hyphens
    name = re.sub(r"[/\\:*?\"<>|#%&{}$!@^`~=+\[\]]", "-", name)

    # Replace spaces and underscores with hyphens for uniformity
    name = re.sub(r"[\s_]+", "-", name)

    # Collapse repeated hyphens and strip leading/trailing
    name = re.sub(r"-+", "-", name).strip("-.")

    # Limit length
    if len(name) > max_length:
        name = name[:max_length].rstrip("-.")

    return name or "document"


def generate_stored_filename(display_name: str, extension: str) -> str:
    """
    Generate a collision-resistant stored filename.

    Pattern: {ISO_timestamp}__{safe_display_name}.{ext}
    Example: 20260614T191200__electricity-bill.pdf
    """
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    safe_name = sanitize_filename(display_name)

    # Ensure extension starts with dot
    if extension and not extension.startswith("."):
        extension = f".{extension}"

    return f"{timestamp}__{safe_name}{extension}"


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def _get_upload_base() -> Path:
    """Base upload directory from env or default."""
    return Path(os.getenv("UPLOAD_DIR", "./uploads"))


def get_user_doc_dir(user_id: str, category: str) -> Path:
    """
    Get (and create) the vault storage directory for a user + category.

    Layout: uploads/user_docs/{user_id}/{category}/
    """
    safe_user_id = sanitize_filename(user_id, max_length=64)
    safe_category = sanitize_filename(category, max_length=32)
    dir_path = _get_upload_base() / "user_docs" / safe_user_id / safe_category
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_temp_session_dir(session_id: str) -> Path:
    """
    Get (and create) the temp storage directory for a session.

    Layout: uploads/temp_sessions/{session_id}/
    """
    safe_sid = sanitize_filename(session_id, max_length=64)
    dir_path = _get_upload_base() / "temp_sessions" / safe_sid
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------

def validate_file_upload(
    file_bytes: bytes,
    filename: str,
    max_size_mb: int = 10,
) -> Tuple[str, str]:
    """
    Validate an uploaded file.

    Returns:
        (mime_type, extension)

    Raises:
        ValueError on validation failure.
    """
    if not file_bytes:
        raise ValueError("Empty file")

    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"File too large: {size_mb:.1f} MB (max {max_size_mb} MB)")

    # Extract and validate extension
    _, ext = os.path.splitext(filename or "")
    ext = ext.lower()

    if ext in BLOCKED_EXTENSIONS:
        raise ValueError(f"File type '{ext}' is not allowed for security reasons")

    # Infer MIME type
    mime_type, _ = mimetypes.guess_type(filename or f"file{ext}")
    if not mime_type:
        mime_type = "application/octet-stream"

    # Secondary extension validation: if no extension, try to infer from content
    if not ext:
        guessed_ext = mimetypes.guess_extension(mime_type)
        ext = guessed_ext or ""

    return mime_type, ext


# ---------------------------------------------------------------------------
# File save operations
# ---------------------------------------------------------------------------

def save_file_to_vault(
    file_bytes: bytes,
    user_id: str,
    category: str,
    display_name: str,
    extension: str,
) -> Tuple[str, str, int]:
    """
    Save a file to the user's vault directory.

    Returns:
        (stored_filename, absolute_storage_path, size_bytes)
    """
    target_dir = get_user_doc_dir(user_id, category)
    stored_filename = generate_stored_filename(display_name, extension)
    file_path = target_dir / stored_filename

    # Handle rare collision by appending counter
    counter = 1
    while file_path.exists():
        base, ext = os.path.splitext(stored_filename)
        file_path = target_dir / f"{base}_{counter}{ext}"
        counter += 1

    # Atomic-ish write: write to temp then rename
    temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    try:
        temp_path.write_bytes(file_bytes)
        temp_path.rename(file_path)
    except Exception:
        # Cleanup temp on failure
        if temp_path.exists():
            temp_path.unlink()
        raise

    abs_path = str(file_path.resolve())
    size_bytes = len(file_bytes)

    # Path traversal check: ensure result is under upload base
    upload_base = str(_get_upload_base().resolve())
    if not abs_path.startswith(upload_base):
        # This should never happen, but guard against it
        file_path.unlink()
        raise ValueError("Path traversal detected — file rejected")

    return file_path.name, abs_path, size_bytes


def save_temp_session_file(
    file_bytes: bytes,
    session_id: str,
    field_name: str,
    extension: str,
) -> Tuple[str, str]:
    """
    Save a file to the temporary session directory (not persisted in vault).

    Returns:
        (stored_filename, absolute_storage_path)
    """
    target_dir = get_temp_session_dir(session_id)
    safe_field = sanitize_filename(field_name, max_length=100)

    if extension and not extension.startswith("."):
        extension = f".{extension}"

    stored_filename = f"{safe_field}{extension}"
    file_path = target_dir / stored_filename

    file_path.write_bytes(file_bytes)
    return stored_filename, str(file_path.resolve())


def cleanup_temp_session(session_id: str) -> None:
    """Remove the temporary session directory and all its contents."""
    safe_sid = sanitize_filename(session_id, max_length=64)
    dir_path = _get_upload_base() / "temp_sessions" / safe_sid
    if dir_path.exists():
        shutil.rmtree(dir_path)
        print(f"[VaultStorage] Cleaned up temp session: {session_id}")


def resolve_document_path(storage_path: str) -> Optional[str]:
    """
    Resolve and verify a document's absolute path exists.
    Returns the absolute path or None if file doesn't exist.
    """
    if not storage_path:
        return None
    path = Path(storage_path)
    if path.exists() and path.is_file():
        return str(path.resolve())
    return None
