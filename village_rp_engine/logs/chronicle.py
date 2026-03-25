from __future__ import annotations

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.phase1_world import ChronicleEntry


def build_chronicle_entries(settlement_state: WorldState) -> list[ChronicleEntry]:
    entries: list[ChronicleEntry] = []
    for event in settlement_state.triggered_events:
        entries.append(
            ChronicleEntry(
                entry_type='event',
                source_id=event.event_id,
                day=settlement_state.day,
                tick=settlement_state.tick,
                text=event.outcome_text,
            )
        )
    for rumor in settlement_state.rumor_log[-3:]:
        entries.append(
            ChronicleEntry(
                entry_type='rumor',
                source_id=rumor.source_event_id,
                day=rumor.day,
                tick=rumor.tick,
                text=rumor.text,
            )
        )
    for line in settlement_state.world_log:
        if not line.startswith(('이벤트 발생:', '상태 부여:', '퀘스트 시작:', '퀘스트 완료:')):
            continue
        entries.append(
            ChronicleEntry(
                entry_type='world_log',
                source_id=None,
                day=settlement_state.day,
                tick=settlement_state.tick,
                text=line,
            )
        )
    return entries
