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
                settlement_id=settlement_state.settlement_id,
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
                settlement_id=settlement_state.settlement_id,
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
                settlement_id=settlement_state.settlement_id,
            )
        )
    return entries


def build_world_chronicle_entries(
    settlement_states: dict[str, WorldState],
    active_settlement_id: str | None = None,
) -> list[ChronicleEntry]:
    entries: list[ChronicleEntry] = []
    ordered_ids = sorted(settlement_states)
    if active_settlement_id in ordered_ids:
        ordered_ids.remove(active_settlement_id)
        ordered_ids.insert(0, active_settlement_id)
    for settlement_id in ordered_ids:
        settlement_state = settlement_states[settlement_id]
        local_entries = build_chronicle_entries(settlement_state)
        if local_entries:
            prioritized_entries = [entry for entry in local_entries if entry.entry_type in {'event', 'rumor'}]
            fallback_entries = [entry for entry in local_entries if entry.entry_type not in {'event', 'rumor'}]
            entries.extend((prioritized_entries or fallback_entries)[-2:])
            continue
        if settlement_state.rumor_log:
            latest_rumor = settlement_state.rumor_log[-1]
            entries.append(
                ChronicleEntry(
                    entry_type='rumor_summary',
                    source_id=latest_rumor.source_event_id,
                    day=latest_rumor.day,
                    tick=latest_rumor.tick,
                    text=f'{settlement_id}: {latest_rumor.text}',
                    settlement_id=settlement_id,
                )
            )
            continue
        entries.append(
            ChronicleEntry(
                entry_type='settlement_summary',
                source_id=None,
                day=settlement_state.day,
                tick=settlement_state.tick,
                text=f'{settlement_id}: visible activity 없음',
                settlement_id=settlement_id,
            )
        )
    return entries[-6:]
