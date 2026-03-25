from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from village_rp_engine.core import mode_controller, world_engine, world_state
from village_rp_engine.core.mode_controller import build_engine, build_world_engine, create_default_state, create_default_world_snapshot
from village_rp_engine.core.world_engine import (
    apply_pending_influences,
    build_presentation_state,
    build_world_snapshot,
    resolve_simulation_depth,
)
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.phase1_world import InfluencePacket, SimulationDepth
from village_rp_engine.models.player_action import PlayerAction


def test_phase1_world_wraps_existing_settlement_engine() -> None:
    settlement_engine = build_engine()
    world = build_world_engine()
    state = create_default_state()
    snapshot = build_world_snapshot(create_default_state())

    expected_state = settlement_engine.run_tick(state, player_action=PlayerAction.move('술집'))
    next_snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.move('술집'))

    assert next_snapshot.settlement_state.tick == expected_state.tick
    assert next_snapshot.settlement_state.time_phase == expected_state.time_phase
    assert next_snapshot.settlement_state.player_location == expected_state.player_location


def test_mode_controller_builds_engine_from_settlement_definition(monkeypatch) -> None:
    called = {'value': False}
    original = mode_controller.build_phase1_settlement

    def fake_build_phase1_settlement():
        called['value'] = True
        return original()

    monkeypatch.setattr(mode_controller, 'build_phase1_settlement', fake_build_phase1_settlement)

    engine = mode_controller.build_engine()

    assert called['value'] is True
    assert engine.event_system.event_definitions


def test_world_state_initializes_from_settlement_definition(monkeypatch) -> None:
    fake_settlement = SimpleNamespace(
        settlement_id='seed_village',
        security=SimpleNamespace(value=77),
        stress_default=13,
        economy_profile=SimpleNamespace(values={'grain': 12, 'iron': 3}),
    )
    monkeypatch.setattr(world_state, '_get_phase1_settlement_definition', lambda: fake_settlement)

    state = world_state.create_initial_world_state()

    assert state.settlement_id == 'seed_village'
    assert state.security == 77
    assert state.stress == 13
    assert state.economy_profile == {'grain': 12, 'iron': 3}


def test_single_settlement_defaults_to_depth_active() -> None:
    snapshot = create_default_world_snapshot()

    assert snapshot.simulation_depth == SimulationDepth.ACTIVE
    assert resolve_simulation_depth('village_1', 'village_1') == SimulationDepth.ACTIVE


def test_influence_packet_apply_is_noop_without_inputs() -> None:
    state = create_default_state()
    before = (dict(state.economy_profile), state.security, state.stress)

    remaining = apply_pending_influences(state, ())

    assert remaining == ()
    assert (state.economy_profile, state.security, state.stress) == before


def test_presentation_layer_still_generates_scene_and_dialogue() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.move('술집'))

    assert snapshot.presentation_state.visible_scenes
    assert '대장장이와 농부' in snapshot.presentation_state.visible_scenes[0]


def test_presentation_state_is_derived_only() -> None:
    snapshot = create_default_world_snapshot()
    rebuilt = build_world_snapshot(
        snapshot.settlement_state,
        simulation_depth=snapshot.simulation_depth,
        pending_influences=snapshot.pending_influences,
    )

    assert rebuilt.presentation_state == build_presentation_state(snapshot.settlement_state)
    assert rebuilt.presentation_state is not snapshot.presentation_state


def test_apply_pending_influences_only_updates_numeric_settlement_fields() -> None:
    state = create_default_state()
    state.player_location = '술집'
    state.relationships[('farmer', 'blacksmith')] = -1
    packet = InfluencePacket(
        source_layer='region',
        target_settlement_id=state.settlement_id,
        economy_delta={'grain': 5},
        security_delta=2,
        stress_delta=-1,
        rumor_tags=('harvest',),
    )

    apply_pending_influences(state, (packet,))

    assert state.economy_profile['grain'] == 85
    assert state.security == 62
    assert state.stress == 19
    assert state.player_location == '술집'
    assert state.relationships[('farmer', 'blacksmith')] == -1


def test_resolve_simulation_depth_preserves_three_branch_shape() -> None:
    assert resolve_simulation_depth('village_1', 'village_1') == SimulationDepth.ACTIVE
    assert resolve_simulation_depth('village_1', 'village_2', recently_visited_ids={'village_2'}) == SimulationDepth.RECENT
    assert resolve_simulation_depth('village_1', 'village_3', recently_visited_ids={'village_2'}) == SimulationDepth.UNVISITED


def test_world_engine_run_step_resolves_depth_via_policy_function(monkeypatch) -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    calls: list[tuple[str, str, set[str]]] = []

    def fake_resolve(active_settlement_id: str, target_settlement_id: str, recently_visited_ids=None):
        calls.append((active_settlement_id, target_settlement_id, set(recently_visited_ids or [])))
        return SimulationDepth.RECENT

    monkeypatch.setattr(world_engine, 'resolve_simulation_depth', fake_resolve)

    next_snapshot = world.run_step(
        snapshot,
        Mode.RP,
        action=PlayerAction.wait(),
        target_settlement_id='village_2',
        recently_visited_ids={'village_2'},
    )

    assert calls == [('village_1', 'village_2', {'village_2'})]
    assert next_snapshot.simulation_depth == SimulationDepth.RECENT
    assert next_snapshot.settlement_state.tick == snapshot.settlement_state.tick


def test_no_raw_seed_builder_usage_in_world_main_webui() -> None:
    target_files = [
        Path(r'D:/Village_RP_Engine/village_rp_engine/core/world_engine.py'),
        Path(r'D:/Village_RP_Engine/village_rp_engine/main.py'),
        Path(r'D:/Village_RP_Engine/web_ui.py'),
    ]

    for target_file in target_files:
        source = target_file.read_text(encoding='utf-8')
        assert 'build_npcs(' not in source


def test_chronicle_entries_are_built_from_settlement_state() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.move('술집'))

    assert snapshot.presentation_state.chronicle_entries
    assert any(entry.entry_type == 'event' for entry in snapshot.presentation_state.chronicle_entries)
