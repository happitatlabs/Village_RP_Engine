from __future__ import annotations

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.phase1_world import ChronicleEntry, ContinentRuntimeState, RegionRuntimeState


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


def build_region_chronicle_entries(
    region_states: dict[str, RegionRuntimeState],
    day: int,
    tick: int,
) -> list[ChronicleEntry]:
    entries: list[ChronicleEntry] = []
    for region_id, region_state in sorted(region_states.items()):
        if region_state.security_risk >= 2:
            text = f'{region_id}: security tension rising'
        elif region_state.rumor_density >= 2:
            text = f'{region_id}: rumor traffic increased'
        else:
            text = f'{region_id}: regional pressure steady'
        entries.append(
            ChronicleEntry(
                entry_type='region_summary',
                source_id=region_id,
                day=day,
                tick=tick,
                text=text,
                settlement_id=None,
            )
        )
    return entries


def build_continent_chronicle_entries(
    continent_states: dict[str, ContinentRuntimeState],
    day: int,
    tick: int,
) -> list[ChronicleEntry]:
    entries: list[ChronicleEntry] = []
    for continent_id, continent_state in sorted(continent_states.items()):
        if continent_state.global_tension >= 2:
            text = f'{continent_id}: rising global tension'
        elif continent_state.trade_pressure >= 2:
            text = f'{continent_id}: trade pressure increasing'
        else:
            text = f'{continent_id}: continental pressure steady'
        entries.append(
            ChronicleEntry(
                entry_type='continent_summary',
                source_id=continent_id,
                day=day,
                tick=tick,
                text=text,
                settlement_id=None,
            )
        )
    return entries


def build_world_chronicle_entries(
    settlement_states: dict[str, WorldState],
    active_settlement_id: str | None = None,
    region_states: dict[str, RegionRuntimeState] | None = None,
    continent_states: dict[str, ContinentRuntimeState] | None = None,
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
    if active_settlement_id in settlement_states:
        summary_day = settlement_states[active_settlement_id].day
        summary_tick = settlement_states[active_settlement_id].tick
    else:
        anchor_state = settlement_states[ordered_ids[0]]
        summary_day = anchor_state.day
        summary_tick = anchor_state.tick
    if region_states:
        entries.extend(build_region_chronicle_entries(region_states, summary_day, summary_tick))
    if continent_states:
        entries.extend(build_continent_chronicle_entries(continent_states, summary_day, summary_tick))
    return entries[-10:]
