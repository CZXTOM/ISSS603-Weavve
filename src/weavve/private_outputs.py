"""Write private analysis artifacts outside Git checkouts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


def private_output_directory(path):
    candidate = Path(path).expanduser().resolve()
    if any((parent / ".git").exists() for parent in [candidate, *candidate.parents]):
        raise ValueError("Private outputs must be outside every Git checkout")
    return candidate


def write_private_json(value, directory, filename):
    if not isinstance(filename, str) or Path(filename).name != filename or not filename.endswith(".json"):
        raise ValueError("Supply one JSON filename without a directory")
    encoded = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    folder = private_output_directory(directory)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / filename
    if destination.is_symlink() or destination.resolve() != destination:
        raise ValueError("Private output must not be a redirected file")
    private_output_directory(destination.resolve().parent)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder,
                                         prefix=".private-write-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return destination
