from __future__ import annotations

from village_rp_engine.config import TIME_PHASES


class TimeSystem:
    def __init__(self, phases: list[str] | None = None) -> None:
        self.phases = phases or TIME_PHASES

    def next_phase(self, current_phase: str) -> str:
        current_index = self.phases.index(current_phase)
        return self.phases[(current_index + 1) % len(self.phases)]
