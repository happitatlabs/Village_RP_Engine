from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Dialogue:
    speaker_id: str
    speaker_name: str
    text: str
    source_type: str = "talk"
