"""
File change tracker for the ChainPilot DE pipeline.

Computes SHA-256 hashes of source files and persists processing status
to data/tracker.json so each file is only reprocessed when its content
actually changes.

Status lifecycle:  (new or changed) → processed → loaded

Usage:
    from etl.file_tracker import FileTracker
    from config import TRACKER_PATH, ROOT

    tracker = FileTracker(TRACKER_PATH, ROOT)
    if tracker.needs_processing(filepath):
        ...do work...
        tracker.mark_processed(filepath, source_id="stock_management")
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class FileTracker:
    """Persist file hashes and processing status across pipeline runs."""

    def __init__(self, tracker_path: Path, root: Path):
        self.path = tracker_path
        self.root = root
        self._state: dict = self._load()

    # ── Persistence ────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        return {"version": 1, "files": {}}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2)

    # ── Internals ──────────────────────────────────────────────────────

    @staticmethod
    def _hash(filepath: Path) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _key(self, filepath: Path) -> str:
        """Stable key: path relative to project root (portable across machines)."""
        try:
            return filepath.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return filepath.as_posix()

    def _entry(self, filepath: Path) -> Optional[dict]:
        return self._state["files"].get(self._key(filepath))

    # ── Queries ────────────────────────────────────────────────────────

    def needs_processing(self, filepath: Path) -> bool:
        """True if the file is new, has changed content, or was never fully processed."""
        if not filepath.exists():
            return False
        entry = self._entry(filepath)
        if entry is None:
            return True
        if entry.get("hash") != self._hash(filepath):
            return True
        return entry.get("status") not in ("processed", "loaded")

    def needs_loading(self, filepath: Path) -> bool:
        """True if the file has been processed but not yet loaded to the database."""
        entry = self._entry(filepath)
        return entry is not None and entry.get("status") == "processed"

    def get_status(self, filepath: Path) -> str:
        """Return current status: pending | processed | loaded."""
        entry = self._entry(filepath)
        return entry.get("status", "pending") if entry else "pending"

    def filter_unprocessed(self, filepaths: list) -> list:
        """Return only the filepaths that need processing."""
        return [f for f in filepaths if self.needs_processing(f)]

    def summary(self) -> dict:
        """Return status counts across all tracked files."""
        counts: dict = {}
        for entry in self._state["files"].values():
            s = entry.get("status", "pending")
            counts[s] = counts.get(s, 0) + 1
        return counts

    # ── Mutations ──────────────────────────────────────────────────────

    def mark_processed(self, filepath: Path, source_id: str = ""):
        """Record that a file has been successfully processed."""
        key = self._key(filepath)
        existing = self._state["files"].get(key, {})
        self._state["files"][key] = {
            **existing,
            "filename": filepath.name,
            "source_id": source_id,
            "hash": self._hash(filepath),
            "size_bytes": filepath.stat().st_size,
            "status": "processed",
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

    def mark_loaded(self, filepath: Path):
        """Record that a file's data has been loaded into the database."""
        key = self._key(filepath)
        entry = self._state["files"].get(key, {})
        entry["status"] = "loaded"
        entry["loaded_at"] = datetime.now(timezone.utc).isoformat()
        self._state["files"][key] = entry
        self._save()

    def reset(self, filepath: Path):
        """Force a file back to pending so it will be reprocessed on the next run."""
        key = self._key(filepath)
        entry = self._state["files"].get(key, {})
        entry["status"] = "pending"
        self._state["files"][key] = entry
        self._save()
