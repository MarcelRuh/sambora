"""HTTP-Hilfen."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import quote

_HOSTNAME_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$",
    re.IGNORECASE,
)
_LOCAL_SUFFIXES = (".local", ".lan", ".home.arpa", ".internal", ".home")
_WILDCARD_BINDS = frozenset({"", "0.0.0.0", "::", "::0"})


def attachment_content_disposition(filename: str) -> str:
    """RFC 6266 Content-Disposition, sicher für Umlaute und Anführungszeichen."""
    name = (filename or "download").replace("\r", "").replace("\n", "").replace("\\", "_")
    name = name.replace('"', "'").strip() or "download"
    ascii_name = name.encode("ascii", "replace").decode("ascii")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name, safe='')}"


def parse_host_header(host_header: str) -> str | None:
    """Hostname ohne Port, oder None bei Header-Injection / unsicherem Format."""
    raw = (host_header or "").strip()
    if not raw or any(ch in raw for ch in "/\\@\r\n\t "):
        return None
    if raw.startswith("["):
        end = raw.find("]")
        if end < 2:
            return None
        host = raw[1:end]
        rest = raw[end + 1 :]
        if rest and not re.fullmatch(r":\d{1,5}", rest):
            return None
        return host or None
    if raw.count(":") == 1:
        host, port = raw.rsplit(":", 1)
        if not port.isdigit() or not host:
            return None
        return host
    return raw


def _is_private_or_loopback(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local)


def _normalize_host(value: str) -> str:
    return value.strip().lower().rstrip(".")


def safe_redirect_hostname(
    host_header: str,
    *,
    bind_host: str = "0.0.0.0",
    public_hostname: str = "",
) -> str:
    """Hostname für HTTP→HTTPS-Redirect – kein Open-Redirect über Host-Header."""
    fallback = "127.0.0.1"
    bind = (bind_host or "").strip()
    if bind not in _WILDCARD_BINDS:
        fallback = bind

    parsed = parse_host_header(host_header)
    if not parsed:
        return fallback

    host = parsed.strip().rstrip(".")
    lower = _normalize_host(host)
    allowed = {"localhost", "127.0.0.1", "::1"}
    if public_hostname:
        allowed.add(_normalize_host(public_hostname))
    if bind not in _WILDCARD_BINDS:
        allowed.add(_normalize_host(bind))

    if lower in allowed:
        return host
    if _is_private_or_loopback(host):
        return host
    if any(lower.endswith(suffix) for suffix in _LOCAL_SUFFIXES) and _HOSTNAME_RE.match(host):
        return host
    return fallback
