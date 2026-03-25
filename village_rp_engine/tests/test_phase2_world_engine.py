from __future__ import annotations

from village_rp_engine.core.mode_controller import build_world_engine, create_default_state, create_default_world_snapshot
from village_rp_engine.core.world_engine import build_world_snapshot, can_travel_between_settlements
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.phase1_world import SettlementLink
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.models.rumor import Rumor


def test_world_snapshot_supports_multiple_settlements() -> None:
    snapshot = create_default_world_snapshot()

    assert len(snapshot.settlement_definitions) >= 3
    assert {'village_1', 'village_2', 'town_1'}.issubset(snapshot.settlement_states)
    assert snapshot.active_settlement_id == 'village_1'


def test_active_settlement_runs_full_interaction_only() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.move('술집'))

    assert snapshot.presentation_state.visible_scenes
    assert snapshot.settlement_states['village_1'].visible_scenes
    assert snapshot.settlement_states['village_2'].visible_scenes == []
    assert snapshot.settlement_states['town_1'].dialogues == []


def test_recent_settlement_uses_lightweight_update() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.travel('village_2'))
    recent_state = snapshot.settlement_states['village_1']

    assert 'recent settlement update' in recent_state.world_log[-1]
    assert recent_state.visible_scenes == []
    assert recent_state.dialogues == []


def test_unvisited_settlement_uses_numeric_only_update() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    unvisited_state = snapshot.settlement_states['town_1']

    assert 'unvisited settlement update' in unvisited_state.world_log[-1]
    assert unvisited_state.visible_scenes == []
    assert unvisited_state.dialogues == []
    assert unvisited_state.triggered_events == []


def test_player_move_between_settlements_updates_active_and_recent() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.travel('village_2'))

    assert snapshot.active_settlement_id == 'village_2'
    assert 'village_1' in snapshot.recently_visited_ids
    assert snapshot.settlement_state.settlement_id == 'village_2'


def test_rumor_propagates_across_settlement_links() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    source_state = snapshot.settlement_states['village_1']
    source_state.rumor_log.append(
        Rumor(
            source_event_id='argument_at_tavern',
            tick=0,
            day=1,
            time_phase='아침',
            location='술집',
            text='술집에서 큰 싸움이 있었다는 말이 돌았다.',
            origin_settlement_id='village_1',
            freshness=3,
            intensity=2,
        )
    )

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    propagated = snapshot.settlement_states['village_2'].rumor_log

    assert any(rumor.is_remote for rumor in propagated)
    assert any('village_1' in rumor.text for rumor in propagated)
    assert snapshot.settlement_states['village_2'].triggered_events == []


def test_chronicle_summarizes_cross_settlement_activity() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot.settlement_states['village_1'].rumor_log.append(
        Rumor(
            source_event_id='argument_at_tavern',
            tick=0,
            day=1,
            time_phase='아침',
            location='술집',
            text='술집에서 말다툼이 있었다는 말이 돌았다.',
            origin_settlement_id='village_1',
            freshness=3,
            intensity=2,
        )
    )

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    assert any(entry.settlement_id == 'village_2' for entry in snapshot.presentation_state.chronicle_entries)
    assert any('village_1' in entry.text for entry in snapshot.presentation_state.chronicle_entries)


def test_phase1_single_settlement_compatibility_still_holds() -> None:
    world = build_world_engine()
    snapshot = build_world_snapshot(create_default_state())

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.move('술집'))

    assert snapshot.settlement_state.player_location == '술집'
    assert snapshot.active_settlement_id == 'village_1'


def test_travel_requires_direct_settlement_link() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = build_world_snapshot(
        settlement_definitions=snapshot.settlement_definitions,
        settlement_states=snapshot.settlement_states,
        active_settlement_id=snapshot.active_settlement_id,
        recently_visited_ids=snapshot.recently_visited_ids,
        settlement_links=(SettlementLink('village_1', 'village_2', 'road', 1, 1, 1),),
    )

    assert can_travel_between_settlements('village_1', 'town_1', snapshot.settlement_links) is False

    next_snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.travel('town_1'))

    assert next_snapshot.active_settlement_id == 'village_1'
    assert next_snapshot.settlement_states['village_1'].player_location is not None
    assert next_snapshot.settlement_states['town_1'].player_location is None


def test_only_active_settlement_has_player_location() -> None:
    snapshot = create_default_world_snapshot()

    assert snapshot.settlement_states['village_1'].player_location is not None
    assert snapshot.settlement_states['village_2'].player_location is None
    assert snapshot.settlement_states['town_1'].player_location is None


def test_player_location_moves_with_active_settlement_transition() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.travel('village_2'))

    assert snapshot.active_settlement_id == 'village_2'
    assert snapshot.settlement_states['village_1'].player_location is None
    assert snapshot.settlement_states['village_2'].player_location is not None
    assert snapshot.settlement_states['town_1'].player_location is None
