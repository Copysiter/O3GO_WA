"""Filesystem checks shared by account reports and maintenance scripts."""

from pathlib import Path


def account_file_exists(directory: Path, file_name: str | None) -> bool:
    """Check for a regular file whose resolved path stays inside storage."""
    if not file_name:
        return False

    base_path = directory.resolve()
    file_path = (base_path / file_name).resolve()
    try:
        file_path.relative_to(base_path)
    except ValueError:
        return False
    return file_path.is_file()
