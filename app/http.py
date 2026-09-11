"""HTTP-Hilfen."""

from __future__ import annotations

from urllib.parse import quote


def attachment_content_disposition(filename: str) -> str:
    """RFC 6266 Content-Disposition, sicher für Umlaute und Anführungszeichen."""
    name = (filename or "download").replace("\r", "").replace("\n", "").replace("\\", "_")
    name = name.replace('"', "'").strip() or "download"
    ascii_name = name.encode("ascii", "replace").decode("ascii")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name, safe='')}"
