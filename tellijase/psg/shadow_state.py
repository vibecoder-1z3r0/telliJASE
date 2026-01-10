"""Shadow copy of AY-3-8914 registers for JAM + FRAME modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable

_REGISTER_NAMES = [
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
]


@dataclass
class ShadowState:
    """Maintains the latest values written to each AY-3-8914 register."""

    registers: Dict[str, int] = field(default_factory=lambda: {name: 0 for name in _REGISTER_NAMES})

    def update(self, **kwargs: int) -> None:
        """Update register values, clamping to 0-255 to mirror hardware byte writes."""

        for key, value in kwargs.items():
            if key not in self.registers:
                raise KeyError(f"Unknown register {key}")
            self.registers[key] = max(0, min(255, int(value)))

    def snapshot(self) -> Dict[str, int]:
        """Return an immutable copy for persistence/export."""

        return dict(self.registers)

    @classmethod
    def from_iterable(cls, items: Iterable[tuple[str, int]]) -> "ShadowState":
        state = cls()
        state.registers.update({k: max(0, min(255, int(v))) for k, v in items})
        return state
