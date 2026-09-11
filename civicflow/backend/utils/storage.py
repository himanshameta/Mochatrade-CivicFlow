import os
import shutil
from pathlib import Path
from typing import Optional


def ensure_directory(path: str) -> Path:
    """
    Ensure a directory exists, create it if it doesn't.
    
    Args:
        path: Directory path
        
    Returns:
        Path object
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_session_docs_dir(session_id: str) -> Path:
    """
    Get the documents directory for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Path to session documents directory
    """
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    docs_dir = Path(upload_dir) / "docs" / session_id
    return ensure_directory(str(docs_dir))


def get_session_scripts_dir() -> Path:
    """
    Get the scripts directory.
    
    Returns:
        Path to scripts directory
    """
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    scripts_dir = Path(upload_dir) / "scripts"
    return ensure_directory(str(scripts_dir))


def get_screenshots_dir() -> Path:
    """
    Get the screenshots directory.
    
    Returns:
        Path to screenshots directory
    """
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    screenshots_dir = Path(upload_dir) / "screenshots"
    return ensure_directory(str(screenshots_dir))


def cleanup_session_files(session_id: str) -> None:
    """
    Clean up all files associated with a session.
    
    Args:
        session_id: Session identifier
    """
    # Remove documents directory
    docs_dir = get_session_docs_dir(session_id)
    if docs_dir.exists():
        shutil.rmtree(docs_dir)
    
    # Remove session script
    scripts_dir = get_session_scripts_dir()
    script_file = scripts_dir / f"{session_id}.py"
    if script_file.exists():
        script_file.unlink()
    
    # Remove retry scripts
    for script_file in scripts_dir.glob(f"{session_id}_*.py"):
        script_file.unlink()
    
    print(f"[Storage] Cleaned up files for session {session_id}")


def get_file_size_mb(file_path: str) -> float:
    """
    Get file size in MB.
    
    Args:
        file_path: Path to file
        
    Returns:
        File size in MB
    """
    return Path(file_path).stat().st_size / (1024 * 1024)


def is_valid_file_type(filename: str, allowed_extensions: list = None) -> bool:
    """
    Check if file type is allowed.
    
    Args:
        filename: Name of the file
        allowed_extensions: List of allowed extensions (default: images, PDFs, text)
        
    Returns:
        True if file type is allowed
    """
    if allowed_extensions is None:
        allowed_extensions = [
            '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif',  # Images
            '.pdf',  # PDF
            '.txt', '.text'  # Text
        ]
    
    ext = Path(filename).suffix.lower()
    return ext in allowed_extensions


if __name__ == "__main__":
    print("=" * 80)
    print("Testing Storage Utility")
    print("=" * 80)
    
    test_session = "test-session-123"
    
    print("\n[Test 1] Creating directories")
    docs_dir = get_session_docs_dir(test_session)
    print(f"✓ Docs directory: {docs_dir}")
    
    scripts_dir = get_session_scripts_dir()
    print(f"✓ Scripts directory: {scripts_dir}")
    
    screenshots_dir = get_screenshots_dir()
    print(f"✓ Screenshots directory: {screenshots_dir}")
    
    print("\n[Test 2] File validation")
    print(f"✓ 'document.pdf' valid: {is_valid_file_type('document.pdf')}")
    print(f"✓ 'image.png' valid: {is_valid_file_type('image.png')}")
    print(f"✓ 'script.exe' valid: {is_valid_file_type('script.exe')}")
    
    print("\n[Test 3] Cleanup")
    cleanup_session_files(test_session)
    print(f"✓ Cleaned up session files")
    
    print("\n" + "=" * 80)
    print("Storage utility tests complete!")
    print("=" * 80)
