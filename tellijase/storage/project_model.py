"""Lightweight data structures describing the .tellijase project format."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

REGISTER_KEYS = [
    "R0",
    "R1",
    "R2",
    "R3",
    "R4",
    "R5",
    "R6",
    "R7",
    "R8",
    "R9",
    "R10",
    "R11",
    "R12",
    "R13",
    "R14",  # Envelope period high byte
    "R15",  # Envelope shape
]

CHANNEL_IDS = ("A", "B", "C", "N")


def _now_str() -> str:
    return datetime.utcnow().isoformat()


def _parse_time(value: Optional[str]) -> str:
    return value or _now_str()


def _clamp_byte(value: int) -> int:
    return max(0, min(255, int(value)))


def _validate_registers(registers: Dict[str, int]) -> Dict[str, int]:
    cleaned: Dict[str, int] = {}
    for key, value in registers.items():
        if key not in REGISTER_KEYS:
            raise ValueError(f"Unknown register key {key}")
        cleaned[key] = _clamp_byte(value)
    return cleaned


@dataclass
class Metadata:
    name: str = "Untitled Project"
    created: str = field(default_factory=_now_str)
    modified: str = field(default_factory=_now_str)
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "created": self.created,
            "modified": self.modified,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Metadata":
        return cls(
            name=data.get("name", "Untitled Project"),
            created=_parse_time(data.get("created")),
            modified=_parse_time(data.get("modified")),
            notes=data.get("notes"),
        )


@dataclass
class JamSession:
    id: str
    name: str
    registers: Dict[str, int] = field(default_factory=dict)
    created: str = field(default_factory=_now_str)
    updated: str = field(default_factory=_now_str)
    notes: Optional[str] = None
    mod_curves: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.registers = _validate_registers(self.registers)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "registers": self.registers,
            "created": self.created,
            "updated": self.updated,
            "notes": self.notes,
            "mod_curves": self.mod_curves,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JamSession":
        return cls(
            id=data["id"],
            name=data.get("name", "Unnamed Session"),
            registers=data.get("registers", {}),
            created=_parse_time(data.get("created")),
            updated=_parse_time(data.get("updated")),
            notes=data.get("notes"),
            mod_curves=data.get("mod_curves", {}),
        )


@dataclass
class TrackEvent:
    frame: int
    duration: int = 1
    period: Optional[int] = None
    volume: Optional[int] = None
    noise_period: Optional[int] = None
    envelope_id: Optional[str] = None
    instrument_id: Optional[str] = None
    noise: Optional[bool] = None

    def __post_init__(self) -> None:
        if self.frame < 0:
            raise ValueError("frame must be >= 0")
        if self.duration <= 0:
            raise ValueError("duration must be > 0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame": self.frame,
            "duration": self.duration,
            "period": self.period,
            "volume": self.volume,
            "noise_period": self.noise_period,
            "envelope_id": self.envelope_id,
            "instrument_id": self.instrument_id,
            "noise": self.noise,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackEvent":
        return cls(
            frame=int(data.get("frame", 0)),
            duration=int(data.get("duration", 1)),
            period=data.get("period"),
            volume=data.get("volume"),
            noise_period=data.get("noise_period"),
            envelope_id=data.get("envelope_id"),
            instrument_id=data.get("instrument_id"),
            noise=data.get("noise"),
        )


@dataclass
class Song:
    id: str
    name: str
    bpm: int = 120
    loop: bool = False
    tracks: Dict[str, List[TrackEvent]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "bpm": self.bpm,
            "loop": self.loop,
            "tracks": {
                channel: [event.to_dict() for event in events]
                for channel, events in self.tracks.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Song":
        tracks_data = {}
        for channel, events in data.get("tracks", {}).items():
            if channel not in CHANNEL_IDS:
                continue
            tracks_data[channel] = [TrackEvent.from_dict(evt) for evt in events]
        return cls(
            id=data["id"],
            name=data.get("name", "Untitled Song"),
            bpm=int(data.get("bpm", 120)),
            loop=bool(data.get("loop", False)),
            tracks=tracks_data,
        )


@dataclass
class Project:
    format_version: int = 1
    meta: Metadata = field(default_factory=Metadata)
    jam_sessions: List[JamSession] = field(default_factory=list)
    songs: List[Song] = field(default_factory=list)

    def touch(self) -> None:
        self.meta.modified = _now_str()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format_version": self.format_version,
            "meta": self.meta.to_dict(),
            "jam_sessions": [session.to_dict() for session in self.jam_sessions],
            "songs": [song.to_dict() for song in self.songs],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        return cls(
            format_version=int(data.get("format_version", 1)),
            meta=Metadata.from_dict(data.get("meta", {})),
            jam_sessions=[JamSession.from_dict(item) for item in data.get("jam_sessions", [])],
            songs=[Song.from_dict(item) for item in data.get("songs", [])],
        )
