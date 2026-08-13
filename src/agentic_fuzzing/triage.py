"""Crash signature extraction and reproducer persistence."""

import hashlib
import re
from pathlib import Path


_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")
_SOURCE_LINE = re.compile(r"(\S+):(\d+)")


def sanitizer_signature(stderr: bytes) -> str:
    """Normalize volatile addresses and retain the first useful report frames."""
    text = stderr.decode("utf-8", errors="replace")
    lines = []
    for line in text.splitlines():
        if "SUMMARY:" in line or line.lstrip().startswith("#"):
            normalized = _ADDRESS.sub("0xADDR", line.strip())
            normalized = _SOURCE_LINE.sub(r"\1:LINE", normalized)
            lines.append(normalized)
    if not lines:
        lines = [line.strip() for line in text.splitlines() if line.strip()][:3]
    return "\n".join(lines) or "unknown"


def signature_id(stderr: bytes) -> str:
    return hashlib.sha256(sanitizer_signature(stderr).encode("utf-8")).hexdigest()[:16]


def save_reproducer(root: Path, signature: str, data: bytes, stderr: bytes) -> Path:
    destination = root / signature
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "input.bin").write_bytes(data)
    (destination / "stderr.txt").write_bytes(stderr)
    return destination