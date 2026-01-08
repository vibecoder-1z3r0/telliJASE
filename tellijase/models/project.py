"""Project model - like telliGRAM's Project pattern."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from .psg_state import PSGState


@dataclass
class JAMSnapshot:
    """A saved PSG state from JAM mode - like telliGRAM's animation frames."""

    name: str
    state: PSGState
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: str = ""  # User annotations

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "name": self.name,
            "state": self.state.to_registers(),
            "timestamp": self.timestamp,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> JAMSnapshot:
        """Deserialize from dict."""
        state = PSGState.from_registers(data.get("state", {}))
        return cls(
            name=data.get("name", "Untitled"),
            state=state,
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            notes=data.get("notes", ""),
        )


@dataclass
class Project:
    """telliJASE project - matches telliGRAM's Project model pattern."""

    name: str = "Untitled"
    created: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    modified: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    jam_snapshots: List[JAMSnapshot] = field(default_factory=list)
    # Future: frame_timeline for FRAME mode sequencing

    def touch(self) -> None:
        """Update modification timestamp - called when project changes."""
        self.modified = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "name": self.name,
            "created": self.created,
            "modified": self.modified,
            "jam_snapshots": [snap.to_dict() for snap in self.jam_snapshots],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Project:
        """Deserialize from dict."""
        snapshots = [
            JAMSnapshot.from_dict(snap) for snap in data.get("jam_snapshots", [])
        ]
        return cls(
            name=data.get("name", "Untitled"),
            created=data.get("created", datetime.utcnow().isoformat()),
            modified=data.get("modified", datetime.utcnow().isoformat()),
            jam_snapshots=snapshots,
        )


__all__ = ["JAMSnapshot", "Project"]
