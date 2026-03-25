from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.phase1_world import (
    ChronicleArchive,
    ChronicleEntry,
    ChronicleQueryResult,
    ChronicleView,
    ComparisonItem,
    ComparisonResult,
    ContinentDefinition,
    ContinentRuntimeState,
    PlayerHistoryEntry,
    RegionDefinition,
    RegionRuntimeState,
    ScopeDiffResult,
    SettlementDefinition,
    WorldSnapshot,
    WorldSummarySnapshot,
)

SECURITY_PATTERN = re.compile(r'security (-?\d+)')
STRESS_PATTERN = re.compile(r'stress (-?\d+)')
ECONOMY_PATTERN = re.compile(r'economy (.+)$')


def _entry_sort_key(entry: ChronicleEntry) -> tuple[int, int, int, str, str]:
    layer_priority = {'settlement': 3, 'region': 2, 'continent': 1}.get(entry.layer, 0)
    return (entry.day, entry.tick, layer_priority, entry.source_id or '', entry.text)


def _sort_entries(entries: tuple[ChronicleEntry, ...] | list[ChronicleEntry]) -> tuple[ChronicleEntry, ...]:
    return tuple(sorted(entries, key=_entry_sort_key, reverse=True))


def _group_entries(entries: tuple[ChronicleEntry, ...], attribute: str) -> dict[str, tuple[ChronicleEntry, ...]]:
    grouped: dict[str, list[ChronicleEntry]] = defaultdict(list)
    for entry in entries:
        scope_id = getattr(entry, attribute)
        if scope_id is None:
            continue
        grouped[scope_id].append(entry)
    return {scope_id: tuple(values) for scope_id, values in grouped.items()}


def _economy_summary(economy_profile: dict[str, int | float]) -> str:
    return ', '.join(f'{key}={value}' for key, value in sorted(economy_profile.items())[:3])


def build_chronicle_entries(
    settlement_state: WorldState,
    settlement_definition: SettlementDefinition | None = None,
    continent_id: str | None = None,
    observed_settlement_id: str | None = None,
) -> list[ChronicleEntry]:
    region_id = settlement_definition.region_id if settlement_definition is not None else None
    observed_directly = settlement_state.settlement_id == observed_settlement_id
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
                region_id=region_id,
                continent_id=continent_id,
                layer='settlement',
                category='EVENT',
                observed_directly=observed_directly,
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
                region_id=region_id,
                continent_id=continent_id,
                layer='settlement',
                category='RUMOR',
                observed_directly=observed_directly,
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
                region_id=region_id,
                continent_id=continent_id,
                layer='settlement',
                category='STATE_CHANGE',
                observed_directly=observed_directly,
            )
        )
    entries.append(
        ChronicleEntry(
            entry_type='settlement_state',
            source_id=settlement_state.settlement_id,
            day=settlement_state.day,
            tick=settlement_state.tick,
            text=(
                f"{settlement_state.settlement_id}: security {settlement_state.security}, "
                f"stress {settlement_state.stress}, economy {_economy_summary(settlement_state.economy_profile)}"
            ),
            settlement_id=settlement_state.settlement_id,
            region_id=region_id,
            continent_id=continent_id,
            layer='settlement',
            category='STATE_CHANGE',
            observed_directly=observed_directly,
        )
    )
    return entries


def build_region_chronicle_entries(
    region_states: dict[str, RegionRuntimeState],
    day: int,
    tick: int,
    region_definitions: dict[str, RegionDefinition] | None = None,
) -> list[ChronicleEntry]:
    entries: list[ChronicleEntry] = []
    for region_id, region_state in sorted(region_states.items()):
        region_definition = (region_definitions or {}).get(region_id)
        if region_state.security_risk >= 2:
            text = f'{region_id}: local tension increased'
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
                region_id=region_id,
                continent_id=region_definition.continent_id if region_definition is not None else None,
                layer='region',
                category='INFLUENCE',
            )
        )
    return entries


def build_continent_chronicle_entries(
    continent_states: dict[str, ContinentRuntimeState],
    day: int,
    tick: int,
    continent_definitions: dict[str, ContinentDefinition] | None = None,
) -> list[ChronicleEntry]:
    entries: list[ChronicleEntry] = []
    for continent_id, continent_state in sorted(continent_states.items()):
        if continent_state.global_tension >= 2:
            text = f'{continent_id}: regional instability rising'
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
                region_id=None,
                continent_id=continent_id if continent_definitions is None or continent_id in continent_definitions else None,
                layer='continent',
                category='INFLUENCE',
            )
        )
    return entries


def _resolve_summary_time(settlement_states: dict[str, WorldState], active_settlement_id: str | None = None) -> tuple[int, int]:
    ordered_ids = sorted(settlement_states)
    if active_settlement_id in settlement_states:
        anchor_state = settlement_states[active_settlement_id]
    else:
        anchor_state = settlement_states[ordered_ids[0]]
    return anchor_state.day, anchor_state.tick


def collect_world_chronicle_entries(
    settlement_states: dict[str, WorldState],
    active_settlement_id: str | None = None,
    settlement_definitions: dict[str, SettlementDefinition] | None = None,
    region_states: dict[str, RegionRuntimeState] | None = None,
    region_definitions: dict[str, RegionDefinition] | None = None,
    continent_states: dict[str, ContinentRuntimeState] | None = None,
    continent_definitions: dict[str, ContinentDefinition] | None = None,
) -> tuple[ChronicleEntry, ...]:
    summary_day, summary_tick = _resolve_summary_time(settlement_states, active_settlement_id)
    entries: list[ChronicleEntry] = []
    for settlement_id, settlement_state in settlement_states.items():
        settlement_definition = (settlement_definitions or {}).get(settlement_id)
        continent_id = None
        if settlement_definition is not None:
            region_definition = (region_definitions or {}).get(settlement_definition.region_id)
            continent_id = region_definition.continent_id if region_definition is not None else None
        entries.extend(build_chronicle_entries(settlement_state, settlement_definition, continent_id, active_settlement_id))
    if region_states:
        entries.extend(build_region_chronicle_entries(region_states, summary_day, summary_tick, region_definitions))
    if continent_states:
        entries.extend(build_continent_chronicle_entries(continent_states, summary_day, summary_tick, continent_definitions))
    return tuple(entries)


def append_chronicle_entries(archive: ChronicleArchive, entries: tuple[ChronicleEntry, ...] | list[ChronicleEntry]) -> ChronicleArchive:
    return archive.append_entries(entries)


def _build_chronicle_view_from_entries(entries: tuple[ChronicleEntry, ...] | list[ChronicleEntry]) -> ChronicleView:
    ordered_entries = _sort_entries(entries)
    return ChronicleView(
        entries_by_time=ordered_entries,
        entries_by_settlement=_group_entries(ordered_entries, 'settlement_id'),
        entries_by_region=_group_entries(ordered_entries, 'region_id'),
        entries_by_continent=_group_entries(ordered_entries, 'continent_id'),
    )


def _build_presentation_entries_from_archive(archive: ChronicleArchive, limit: int) -> list[ChronicleEntry]:
    ordered_entries = _sort_entries(archive.entries)
    summary_entry_types = {'region_summary', 'continent_summary', 'settlement_state'}
    seen_summary_keys: set[tuple[str, str | None, str | None, str | None]] = set()
    surface_entries: list[ChronicleEntry] = []
    for entry in ordered_entries:
        if entry.entry_type in summary_entry_types:
            key = (entry.entry_type, entry.settlement_id, entry.region_id, entry.continent_id)
            if key in seen_summary_keys:
                continue
            seen_summary_keys.add(key)
        surface_entries.append(entry)
        if len(surface_entries) >= limit:
            break
    return surface_entries


def build_chronicle_view(snapshot: WorldSnapshot) -> ChronicleView:
    current_entries = collect_world_chronicle_entries(
        snapshot.settlement_states,
        active_settlement_id=snapshot.active_settlement_id,
        settlement_definitions=snapshot.settlement_definitions,
        region_states=snapshot.region_states,
        region_definitions=snapshot.region_definitions,
        continent_states=snapshot.continent_states,
        continent_definitions=snapshot.continent_definitions,
    )
    effective_archive = append_chronicle_entries(snapshot.chronicle_archive, current_entries)
    return _build_chronicle_view_from_entries(effective_archive.entries)


def build_world_chronicle_entries(
    settlement_states: dict[str, WorldState],
    active_settlement_id: str | None = None,
    settlement_definitions: dict[str, SettlementDefinition] | None = None,
    region_states: dict[str, RegionRuntimeState] | None = None,
    region_definitions: dict[str, RegionDefinition] | None = None,
    continent_states: dict[str, ContinentRuntimeState] | None = None,
    continent_definitions: dict[str, ContinentDefinition] | None = None,
    chronicle_archive: ChronicleArchive | None = None,
    limit: int = 10,
) -> list[ChronicleEntry]:
    current_entries = collect_world_chronicle_entries(
        settlement_states,
        active_settlement_id=active_settlement_id,
        settlement_definitions=settlement_definitions,
        region_states=region_states,
        region_definitions=region_definitions,
        continent_states=continent_states,
        continent_definitions=continent_definitions,
    )
    archive = append_chronicle_entries(chronicle_archive or ChronicleArchive(), current_entries)
    return _build_presentation_entries_from_archive(archive, limit)


def build_world_summary_snapshot(
    snapshot: WorldSnapshot,
    day: int | None = None,
    tick: int | None = None,
) -> WorldSummarySnapshot:
    summary_day = snapshot.settlement_state.day if day is None else day
    summary_tick = snapshot.settlement_state.tick if tick is None else tick
    settlement_summaries = tuple(
        f"{settlement_id}: security {state.security}, stress {state.stress}, economy {_economy_summary(state.economy_profile)}"
        for settlement_id, state in sorted(snapshot.settlement_states.items())
    )
    region_summaries = tuple(
        entry.text
        for entry in build_region_chronicle_entries(
            snapshot.region_states,
            summary_day,
            summary_tick,
            snapshot.region_definitions,
        )
    )
    continent_summaries = tuple(
        entry.text
        for entry in build_continent_chronicle_entries(
            snapshot.continent_states,
            summary_day,
            summary_tick,
            snapshot.continent_definitions,
        )
    )
    return WorldSummarySnapshot(
        day=summary_day,
        tick=summary_tick,
        settlement_summaries=settlement_summaries,
        region_summaries=region_summaries,
        continent_summaries=continent_summaries,
    )


def _filter_entries(
    entries: tuple[ChronicleEntry, ...],
    *,
    category: str | None = None,
    layer: str | None = None,
    scope: str | None = None,
    settlement_id: str | None = None,
    region_id: str | None = None,
    continent_id: str | None = None,
    keyword: str | None = None,
    start: tuple[int, int] | None = None,
    end: tuple[int, int] | None = None,
) -> tuple[ChronicleEntry, ...]:
    keyword_text = keyword.lower() if keyword else None
    filtered: list[ChronicleEntry] = []
    for entry in entries:
        if category and entry.category != category:
            continue
        if layer and entry.layer != layer:
            continue
        if scope == 'settlement' and entry.settlement_id is None:
            continue
        if scope == 'region' and entry.region_id is None:
            continue
        if scope == 'continent' and entry.continent_id is None:
            continue
        if settlement_id and entry.settlement_id != settlement_id:
            continue
        if region_id and entry.region_id != region_id:
            continue
        if continent_id and entry.continent_id != continent_id:
            continue
        if keyword_text and keyword_text not in entry.text.lower():
            continue
        if start and (entry.day, entry.tick) < start:
            continue
        if end and (entry.day, entry.tick) > end:
            continue
        filtered.append(entry)
    return tuple(filtered)


def _query_description(
    *,
    category: str | None,
    layer: str | None,
    scope: str | None,
    settlement_id: str | None,
    region_id: str | None,
    continent_id: str | None,
    keyword: str | None,
    start: tuple[int, int] | None,
    end: tuple[int, int] | None,
) -> str:
    parts = ['history query']
    if category:
        parts.append(f'category={category}')
    if layer:
        parts.append(f'layer={layer}')
    if scope:
        parts.append(f'scope={scope}')
    if settlement_id:
        parts.append(f'settlement={settlement_id}')
    if region_id:
        parts.append(f'region={region_id}')
    if continent_id:
        parts.append(f'continent={continent_id}')
    if keyword:
        parts.append(f'keyword={keyword}')
    if start or end:
        parts.append(f'range={start}->{end}')
    return ' | '.join(parts)


@dataclass(frozen=True)
class ChronicleQuery:
    snapshot: WorldSnapshot
    view: ChronicleView

    def query_entries(
        self,
        *,
        category: str | None = None,
        layer: str | None = None,
        scope: str | None = None,
        settlement_id: str | None = None,
        region_id: str | None = None,
        continent_id: str | None = None,
        keyword: str | None = None,
        start: tuple[int, int] | None = None,
        end: tuple[int, int] | None = None,
        limit: int | None = None,
    ) -> ChronicleQueryResult:
        filtered_entries = _filter_entries(
            self.view.entries_by_time,
            category=category,
            layer=layer,
            scope=scope,
            settlement_id=settlement_id,
            region_id=region_id,
            continent_id=continent_id,
            keyword=keyword,
            start=start,
            end=end,
        )
        total_count = len(filtered_entries)
        if limit is not None:
            filtered_entries = filtered_entries[:limit]
        return ChronicleQueryResult(
            entries=filtered_entries,
            total_count=total_count,
            query_description=_query_description(
                category=category,
                layer=layer,
                scope=scope,
                settlement_id=settlement_id,
                region_id=region_id,
                continent_id=continent_id,
                keyword=keyword,
                start=start,
                end=end,
            ),
        )

    def get_entries_between(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        *,
        limit: int | None = None,
    ) -> ChronicleQueryResult:
        return self.query_entries(start=start, end=end, limit=limit)


def build_chronicle_query(snapshot: WorldSnapshot) -> ChronicleQuery:
    return ChronicleQuery(snapshot=snapshot, view=build_chronicle_view(snapshot))


def _get_scope_history(view: ChronicleView, scope_type: str, scope_id: str) -> tuple[ChronicleEntry, ...]:
    if scope_type == 'settlement':
        return view.get_settlement_history(scope_id)
    if scope_type == 'region':
        return view.get_region_history(scope_id)
    if scope_type == 'continent':
        return view.get_continent_history(scope_id)
    return ()


def _parse_state_metrics(entry: ChronicleEntry) -> dict[str, str]:
    metrics: dict[str, str] = {}
    security_match = SECURITY_PATTERN.search(entry.text)
    stress_match = STRESS_PATTERN.search(entry.text)
    economy_match = ECONOMY_PATTERN.search(entry.text)
    if security_match:
        metrics['security'] = security_match.group(1)
    if stress_match:
        metrics['stress'] = stress_match.group(1)
    if economy_match:
        metrics['economy'] = economy_match.group(1)
    return metrics


def build_scope_diff(
    snapshot: WorldSnapshot,
    scope_type: str,
    scope_id: str,
    start: tuple[int, int],
    end: tuple[int, int],
) -> ScopeDiffResult:
    query = build_chronicle_query(snapshot)
    entries = _get_scope_history(query.view, scope_type, scope_id)
    ranged_entries = tuple(
        entry for entry in entries if start <= (entry.day, entry.tick) <= end
    )
    if not ranged_entries:
        return ScopeDiffResult(
            scope_type=scope_type,
            scope_id=scope_id,
            start=start,
            end=end,
            summary_lines=(f'{scope_id}: no recorded changes in range',),
            entry_count=0,
        )

    category_counts = Counter(entry.category for entry in ranged_entries)
    ordered_entries = tuple(sorted(ranged_entries, key=lambda entry: (entry.day, entry.tick)))
    summary_lines = [
        f'{scope_id}: {len(ranged_entries)} changes between Day {start[0]} Tick {start[1]} and Day {end[0]} Tick {end[1]}',
        'categories: ' + ', '.join(f'{category}={count}' for category, count in sorted(category_counts.items())),
    ]
    numeric_state_entries = []
    for entry in ordered_entries:
        metrics = _parse_state_metrics(entry)
        if {'security', 'stress', 'economy'}.issubset(metrics):
            numeric_state_entries.append((entry, metrics))
    if numeric_state_entries:
        first_entry, first_metrics = numeric_state_entries[0]
        last_entry, last_metrics = numeric_state_entries[-1]
        summary_lines.append(
            f"security {first_metrics['security']} -> {last_metrics['security']}, "
            f"stress {first_metrics['stress']} -> {last_metrics['stress']}"
        )
        summary_lines.append(f"latest economy: {last_metrics['economy']}")
    else:
        summary_lines.append(f'latest: {ordered_entries[-1].text}')
    return ScopeDiffResult(
        scope_type=scope_type,
        scope_id=scope_id,
        start=start,
        end=end,
        summary_lines=tuple(summary_lines),
        entry_count=len(ranged_entries),
    )


def build_trend_summary(
    snapshot: WorldSnapshot,
    scope_type: str,
    scope_id: str,
    start: tuple[int, int],
    end: tuple[int, int],
) -> tuple[str, ...]:
    return build_scope_diff(snapshot, scope_type, scope_id, start, end).summary_lines


def _build_comparison_result(snapshot: WorldSnapshot, scope_type: str, scope_ids: list[str] | tuple[str, ...]) -> ComparisonResult:
    query = build_chronicle_query(snapshot)
    items: list[ComparisonItem] = []
    summary_lines: list[str] = []
    for scope_id in scope_ids:
        entries = _get_scope_history(query.view, scope_type, scope_id)
        recent_entries = entries[:6]
        category_counts = Counter(entry.category for entry in recent_entries)
        item_lines = [f'{scope_id}: {len(recent_entries)} recent changes']
        if category_counts:
            item_lines.append(', '.join(f'{category}={count}' for category, count in sorted(category_counts.items())))
        latest_summary = next((entry.text for entry in recent_entries if entry.entry_type in {'settlement_state', 'region_summary', 'continent_summary'}), None)
        if latest_summary:
            item_lines.append(latest_summary)
        items.append(
            ComparisonItem(
                scope_id=scope_id,
                recent_change_count=len(recent_entries),
                category_counts=tuple(sorted(category_counts.items())),
                summary_lines=tuple(item_lines),
            )
        )
        summary_lines.extend(item_lines)
    return ComparisonResult(scope_type=scope_type, items=tuple(items), summary_lines=tuple(summary_lines))


def compare_settlements(snapshot: WorldSnapshot, settlement_ids: list[str] | tuple[str, ...]) -> ComparisonResult:
    return _build_comparison_result(snapshot, 'settlement', settlement_ids)


def compare_regions(snapshot: WorldSnapshot, region_ids: list[str] | tuple[str, ...]) -> ComparisonResult:
    return _build_comparison_result(snapshot, 'region', region_ids)


def compare_continents(snapshot: WorldSnapshot, continent_ids: list[str] | tuple[str, ...]) -> ComparisonResult:
    return _build_comparison_result(snapshot, 'continent', continent_ids)


def get_player_timeline(snapshot: WorldSnapshot, limit: int = 10) -> tuple[PlayerHistoryEntry, ...]:
    view = build_chronicle_view(snapshot)
    relevant_entries = view.get_player_recent_history(
        snapshot.active_settlement_id,
        snapshot.recently_visited_ids,
        limit=limit,
    )
    timeline: list[PlayerHistoryEntry] = []
    for entry in relevant_entries[:limit]:
        direct = entry.observed_directly
        timeline.append(
            PlayerHistoryEntry(
                entry=entry,
                direct=direct,
                indirect=not direct,
                perspective='observed' if direct else 'reported',
            )
        )
    return tuple(timeline)


def get_player_recent_history(snapshot: WorldSnapshot, limit: int = 10) -> tuple[ChronicleEntry, ...]:
    return tuple(item.entry for item in get_player_timeline(snapshot, limit=limit))
