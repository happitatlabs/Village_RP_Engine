from __future__ import annotations

from village_rp_engine.core.mode_controller import (
    build_world_engine,
    create_default_state,
    create_default_world_snapshot,
)
from village_rp_engine.core.world_engine import build_world_snapshot
from village_rp_engine.logs.chronicle import (
    build_chronicle_view,
    build_world_summary_snapshot,
    get_player_recent_history,
)
from village_rp_engine.models.event import TriggeredEvent
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.models.rumor import Rumor


def test_chronicle_archive_persists_across_ticks() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    archive_after_first = snapshot.chronicle_archive
    first_entries = archive_after_first.entries

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    assert first_entries
    assert len(snapshot.chronicle_archive.entries) >= len(first_entries)
    assert set(first_entries).issubset(set(snapshot.chronicle_archive.entries))


def test_chronicle_view_reads_from_archive() -> None:
    snapshot = create_default_world_snapshot()
    snapshot.settlement_states['village_1'].triggered_events.append(
        TriggeredEvent(
            event_id='argument_at_tavern',
            time_phase='낮',
            location='술집',
            actor_ids=('blacksmith', 'farmer'),
            outcome_text='술집에서 말다툼이 벌어졌다.',
            rumor_text='술집에서 다툼이 있었다는 소문이 퍼졌다.',
            narration_text='말다툼이 벌어졌다.',
            observer_narration_text='말다툼이 벌어지고 있었다.',
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
    snapshot.settlement_states['village_1'].triggered_events = []
    snapshot.settlement_states['village_1'].world_log = []

    view = build_chronicle_view(snapshot)

    assert any(entry.entry_type == 'event' and entry.source_id == 'argument_at_tavern' for entry in view.entries_by_time)


def test_event_history_survives_runtime_reset() -> None:
    snapshot = create_default_world_snapshot()
    snapshot.settlement_states['village_1'].triggered_events.append(
        TriggeredEvent(
            event_id='argument_at_tavern',
            time_phase='낮',
            location='술집',
            actor_ids=('blacksmith', 'farmer'),
            outcome_text='술집에서 말다툼이 벌어졌다.',
            rumor_text='술집에서 다툼이 있었다는 소문이 퍼졌다.',
            narration_text='말다툼이 벌어졌다.',
            observer_narration_text='말다툼이 벌어지고 있었다.',
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
    snapshot.settlement_states['village_1'].triggered_events = []
    snapshot.settlement_states['village_1'].world_log = []
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

    assert any(entry.entry_type == 'event' for entry in snapshot.chronicle_archive.entries)


def test_player_history_includes_while_away_events() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.travel('village_2'))
    snapshot.settlement_states['village_1'].rumor_log.append(
        Rumor(
            source_event_id='argument_at_tavern',
            tick=snapshot.settlement_states['village_1'].tick + 1,
            day=snapshot.settlement_states['village_1'].day,
            time_phase=snapshot.settlement_states['village_1'].time_phase,
            location='술집',
            text='village_1 부재 중 변화',
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

    player_history = get_player_recent_history(snapshot, limit=12)

    assert any(entry.settlement_id == 'village_1' and '부재 중 변화' in entry.text for entry in player_history)


def test_compatibility_path_uses_full_chronicle_surface() -> None:
    snapshot = build_world_snapshot(create_default_state())

    assert any(entry.layer == 'region' for entry in snapshot.presentation_state.chronicle_entries)
    assert any(entry.layer == 'continent' for entry in snapshot.presentation_state.chronicle_entries)
    assert any(entry.region_id is not None for entry in snapshot.presentation_state.chronicle_entries if entry.layer == 'settlement')


def test_world_summary_snapshot_remains_current_state_only() -> None:
    snapshot = create_default_world_snapshot()
    snapshot.settlement_states['village_1'].security = 71
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

    summary = build_world_summary_snapshot(snapshot)

    assert any('security 55' in line for line in summary.settlement_summaries)
    assert all('security 71' not in line for line in summary.settlement_summaries)


def test_chronicle_archive_does_not_modify_world_state() -> None:
    snapshot = create_default_world_snapshot()
    before = {
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

    view = build_chronicle_view(snapshot)
    summary = build_world_summary_snapshot(snapshot)
    player_history = get_player_recent_history(snapshot)

    after = {
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

    assert view.entries_by_time is not None
    assert summary.settlement_summaries is not None
    assert player_history is not None
    assert before == after
