from __future__ import annotations

from pathlib import Path

import aiofiles

from app.config import settings


def _base() -> Path:
    path = Path(settings.STORAGE_BASE_PATH).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_join(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Path traversal attempt blocked") from exc
    return candidate


def job_dir(job_id: str) -> Path:
    path = _safe_join(_base(), job_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _uploads_dir(job_id: str) -> Path:
    path = _safe_join(job_dir(job_id), "uploads")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _outputs_dir(job_id: str) -> Path:
    path = _safe_join(job_dir(job_id), "outputs")
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_upload(job_id: str, filename: str, file_bytes: bytes) -> str:
    safe_name = Path(filename).name  # strip any path components
    dest = _safe_join(_uploads_dir(job_id), safe_name)
    async with aiofiles.open(dest, "wb") as f:
        await f.write(file_bytes)
    return str(dest)


async def save_output(job_id: str, filename: str, content: bytes | str) -> str:
    safe_name = Path(filename).name
    dest = _safe_join(_outputs_dir(job_id), safe_name)
    mode = "wb" if isinstance(content, bytes) else "w"
    async with aiofiles.open(dest, mode) as f:
        await f.write(content)
    return str(dest)


async def read_file(path: str) -> bytes:
    base = _base()
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError("Requested file is outside STORAGE_BASE_PATH") from exc
    async with aiofiles.open(resolved, "rb") as f:
        return await f.read()
