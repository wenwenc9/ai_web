import os
from pathlib import Path


def home_dir() -> Path:
    raw = os.environ.get("SOF_HOME")
    if raw:
        return Path(raw)
    return Path.home() / ".sofreight"


def credentials_path() -> Path:
    """User home credentials — never under the skill package folder."""
    return home_dir() / "credentials.json"


def exports_dir() -> Path:
    return home_dir() / "exports"
