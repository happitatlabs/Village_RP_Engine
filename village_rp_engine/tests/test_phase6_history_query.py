from __future__ import annotations

from collections import deque

import village_rp_engine.main as main_module
from village_rp_engine.core.mode_controller import build_world_engine, create_default_world_snapshot
from village_rp_engine.core.world_engine import build_world_snapshot
from village_rp_engine.logs.chronicle import (
    build_chronicle_query,
    build_scope_diff,
    compare_settlements,
    get_player_timeline,
)
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.models.rumor import Rumor
from web_ui import serialize_snapshot


def test_chronicle_query_filters_by_category_and_scope() -> None:
    snapshot = create_default_world_snapshot()
    state = snapshot.settlement_states['village_1']
    state.rumor_log.append(
        Rumor(
            source_event_id='argument_at_tavern',
            tick=state.tick,
            day=state.day,
            time_phase=state.time_phase,
            location='술집',
            text='village_1 rumor entry',
            origin_settlement_id='village_1',
        )
    )
    snapshot = build_world_snapshot(
        settlement_definitions=snapshot.settlement_definitions,
        settlement_states=snapshot.settlement_states,
        active_settlement_id=snapshot.active_settlement_id,
        recently_visited_ids=snapshot.recently_visited_ids,
        settlement_links=snapshot.settlement_links,
        region_definitions=snapshot.region_definitions,
        region_states=snapshot.region_states,
        continent_definitions=snapshot.continent_definitions,
        continent_states=snapshot.continent_states,
        chronicle_archive=snapshot.chronicle_archive,
    )

    result = build_chronicle_query(snapshot).query_entries(category='RUMOR', settlement_id='village_1')

    assert result.entries
    assert all(entry.category == 'RUMOR' for entry in result.entries)
    assert all(entry.settlement_id == 'village_1' for entry in result.entries)


def test_chronicle_query_supports_time_range() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    range_end = (snapshot.settlement_state.day, snapshot.settlement_state.tick)
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    result = build_chronicle_query(snapshot).get_entries_between((1, 0), range_end)

    assert result.entries
    assert all((1, 0) <= (entry.day, entry.tick) <= range_end for entry in result.entries)


def test_scope_diff_summarizes_changes_between_times() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    diff = build_scope_diff(snapshot, 'settlement', 'village_1', (1, 0), (snapshot.settlement_state.day, snapshot.settlement_state.tick))

    assert diff.entry_count >= 1
    assert diff.summary_lines
    assert 'village_1' in diff.summary_lines[0]


def test_compare_settlements_returns_readable_comparison() -> None:
    snapshot = create_default_world_snapshot()

    comparison = compare_settlements(snapshot, ['village_1', 'village_2'])

    assert len(comparison.items) == 2
    assert comparison.summary_lines
    assert all(item.summary_lines for item in comparison.items)


def test_player_timeline_distinguishes_direct_and_indirect_history() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    active_state = snapshot.settlement_states['village_1']
    active_state.rumor_log.append(
        Rumor(
            source_event_id='argument_at_tavern',
            tick=active_state.tick,
            day=active_state.day,
            time_phase=active_state.time_phase,
            location='술집',
            text='directly observed rumor',
            origin_settlement_id='village_1',
        )
    )
    snapshot = build_world_snapshot(
        settlement_definitions=snapshot.settlement_definitions,
        settlement_states=snapshot.settlement_states,
        active_settlement_id=snapshot.active_settlement_id,
        recently_visited_ids=snapshot.recently_visited_ids,
        settlement_links=snapshot.settlement_links,
        region_definitions=snapshot.region_definitions,
        region_states=snapshot.region_states,
        continent_definitions=snapshot.continent_definitions,
        continent_states=snapshot.continent_states,
        chronicle_archive=snapshot.chronicle_archive,
    )
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.travel('village_2'))
    away_state = snapshot.settlement_states['village_1']
    away_state.rumor_log.append(
        Rumor(
            source_event_id='argument_at_tavern',
            tick=away_state.tick + 1,
            day=away_state.day,
            time_phase=away_state.time_phase,
            location='술집',
            text='while away rumor',
            origin_settlement_id='village_1',
        )
    )
    snapshot = build_world_snapshot(
        settlement_definitions=snapshot.settlement_definitions,
        settlement_states=snapshot.settlement_states,
        active_settlement_id=snapshot.active_settlement_id,
        recently_visited_ids=snapshot.recently_visited_ids,
        settlement_links=snapshot.settlement_links,
        region_definitions=snapshot.region_definitions,
        region_states=snapshot.region_states,
        continent_definitions=snapshot.continent_definitions,
        continent_states=snapshot.continent_states,
        chronicle_archive=snapshot.chronicle_archive,
    )

    timeline = get_player_timeline(snapshot, limit=12)

    assert any(item.direct and 'directly observed rumor' in item.entry.text for item in timeline)
    assert any(item.indirect and 'while away rumor' in item.entry.text for item in timeline)


def test_cli_history_commands_use_query_layer(monkeypatch) -> None:
    snapshot = create_default_world_snapshot()
    outputs: list[str] = []
    inputs = deque(['history compare region north_fields river_trade', 'history compare continent continent_1', 'wait'])
    call_count = 0
    original = main_module.build_chronicle_query

    def wrapped(current_snapshot):
        nonlocal call_count
        call_count += 1
        return original(current_snapshot)

    monkeypatch.setattr(main_module, 'build_chronicle_query', wrapped)

    action = main_module.prompt_player_action(
        [location for location in snapshot.settlement_definition.locations if location != '집'],
        list(snapshot.settlement_definition.npc_ids),
        current_location=snapshot.settlement_state.player_location,
        travel_targets=['village_2'],
        history_snapshot=snapshot,
        input_func=lambda _: inputs.popleft(),
        output_func=outputs.append,
    )

    assert action == PlayerAction.wait()
    assert call_count >= 2
    assert any('comparison (region): north_fields vs river_trade' in line for line in outputs)
    assert any('comparison (continent): continent_1' in line for line in outputs)


def test_web_ui_history_surface_reads_query_results() -> None:
    payload = serialize_snapshot(create_default_world_snapshot())

    assert 'history_surface' in payload
    assert payload['history_surface']['recent']['entries']
    assert payload['history_surface']['comparison']['summary_lines']
    assert payload['history_surface']['region_comparison']['summary_lines']
    assert payload['history_surface']['continent_comparison']['summary_lines']
    assert any('[Region Comparison]' == line for line in payload['chronicle_lines'])
    assert any('[Continent Comparison]' == line for line in payload['chronicle_lines'])


def test_query_layer_does_not_modify_archive_or_world_state() -> None:
    snapshot = create_default_world_snapshot()
    before_archive = snapshot.chronicle_archive.entries
    before_state = {
        settlement_id: (
            state.day,
            state.tick,
            state.security,
            state.stress,
            tuple(state.world_log),
            tuple((rumor.day, rumor.tick, rumor.text) for rumor in state.rumor_log),
        )
        for settlement_id, state in snapshot.settlement_states.items()
    }

    query = build_chronicle_query(snapshot)
    _ = query.query_entries(category='INFLUENCE')
    _ = query.get_entries_between((1, 0), (snapshot.settlement_state.day, snapshot.settlement_state.tick))
    _ = build_scope_diff(snapshot, 'settlement', snapshot.active_settlement_id, (1, 0), (snapshot.settlement_state.day, snapshot.settlement_state.tick))
    _ = compare_settlements(snapshot, ['village_1', 'village_2'])
    _ = get_player_timeline(snapshot, limit=6)

    after_state = {
        settlement_id: (
            state.day,
            state.tick,
            state.security,
            state.stress,
            tuple(state.world_log),
            tuple((rumor.day, rumor.tick, rumor.text) for rumor in state.rumor_log),
        )
        for settlement_id, state in snapshot.settlement_states.items()
    }

    assert snapshot.chronicle_archive.entries == before_archive
    assert before_state == after_state


def test_scope_diff_uses_numeric_state_entries_only() -> None:
    snapshot = create_default_world_snapshot()
    state = snapshot.settlement_states['village_1']
    state.day = 1
    state.tick = 1
    state.world_log.append('퀘스트 시작: noisy state change text')
    snapshot = build_world_snapshot(
        settlement_definitions=snapshot.settlement_definitions,
        settlement_states=snapshot.settlement_states,
        active_settlement_id=snapshot.active_settlement_id,
        recently_visited_ids=snapshot.recently_visited_ids,
        settlement_links=snapshot.settlement_links,
        region_definitions=snapshot.region_definitions,
        region_states=snapshot.region_states,
        continent_definitions=snapshot.continent_definitions,
        continent_states=snapshot.continent_states,
        chronicle_archive=snapshot.chronicle_archive,
    )
    snapshot.settlement_states['village_1'].security = 55
    snapshot.settlement_states['village_1'].stress = 14
    snapshot.settlement_states['village_1'].day = 1
    snapshot.settlement_states['village_1'].tick = 2
    snapshot = build_world_snapshot(
        settlement_definitions=snapshot.settlement_definitions,
        settlement_states=snapshot.settlement_states,
        active_settlement_id=snapshot.active_settlement_id,
        recently_visited_ids=snapshot.recently_visited_ids,
        settlement_links=snapshot.settlement_links,
        region_definitions=snapshot.region_definitions,
        region_states=snapshot.region_states,
        continent_definitions=snapshot.continent_definitions,
        continent_states=snapshot.continent_states,
        chronicle_archive=snapshot.chronicle_archive,
    )

    diff = build_scope_diff(snapshot, 'settlement', 'village_1', (1, 0), (1, 2))

    assert any('security ' in line and '->' in line for line in diff.summary_lines)
    assert any('latest economy:' in line for line in diff.summary_lines)
