from __future__ import annotations

from collections import deque

import village_rp_engine.core.world_engine as world_engine_module
from village_rp_engine.core.mode_controller import (
    build_tick_engine_from_settlement,
    build_world_engine,
    create_default_world_snapshot,
)
from village_rp_engine.core.world_engine import (
    Phase1WorldEngine,
    load_world_state,
    load_world_state_from_slot,
    reset_world_to_seed,
    save_world_state,
    save_world_state_to_slot,
)
from village_rp_engine.domain.settlement_data import build_phase2_settlements, build_phase3_regions, build_phase4_continent
from village_rp_engine.main import prompt_player_action
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.player_action import PlayerAction


def _load_with_engine(world_engine, saved_data):
    return load_world_state(
        saved_data,
        settlement_definitions=world_engine.settlement_definitions,
        settlement_links=world_engine.settlement_links,
        region_definitions=world_engine.region_definitions,
        continent_definitions=world_engine.continent_definitions,
    )


def test_reset_restores_initial_seed_state() -> None:
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    reset_snapshot = reset_world_to_seed(world_engine)

    assert reset_snapshot.active_settlement_id == 'village_1'
    assert reset_snapshot.settlement_state.day == 1
    assert reset_snapshot.settlement_state.tick == 0
    assert reset_snapshot.settlement_state.player_location == '광장'


def test_save_and_load_restore_runtime_state() -> None:
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.travel('village_2'))

    saved_data = save_world_state(snapshot)
    loaded_snapshot = _load_with_engine(world_engine, saved_data)

    assert save_world_state(loaded_snapshot) == saved_data


def test_save_and_load_preserve_chronicle_archive() -> None:
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    saved_data = save_world_state(snapshot)
    loaded_snapshot = _load_with_engine(world_engine, saved_data)

    assert loaded_snapshot.chronicle_archive.entries == snapshot.chronicle_archive.entries
    assert len(loaded_snapshot.chronicle_archive.entries) > 0


def test_reset_clears_archive() -> None:
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    reset_snapshot = reset_world_to_seed(world_engine)

    assert snapshot.chronicle_archive.entries
    assert reset_snapshot.chronicle_archive.entries == ()


def test_player_state_restored_on_load() -> None:
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.travel('village_2'))
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.move('술집'))

    saved_data = save_world_state(snapshot)
    loaded_snapshot = _load_with_engine(world_engine, saved_data)

    assert loaded_snapshot.active_settlement_id == 'village_2'
    assert loaded_snapshot.settlement_states['village_2'].player_location == '술집'
    assert loaded_snapshot.settlement_states['village_1'].player_location is None


def test_save_load_does_not_modify_seed() -> None:
    world_engine = build_world_engine()
    seed_before = dict(world_engine.settlement_definitions)
    snapshot = create_default_world_snapshot()

    saved_data = save_world_state(snapshot)
    loaded_snapshot = _load_with_engine(world_engine, saved_data)

    assert world_engine.settlement_definitions == seed_before
    assert loaded_snapshot.settlement_definitions == seed_before


def test_reset_uses_current_engine_seed_instead_of_default_world() -> None:
    settlements = build_phase2_settlements()
    continent = build_phase4_continent()
    custom_engine = Phase1WorldEngine(
        settlement_definitions={'town_1': settlements['town_1']},
        settlement_engines={'town_1': build_tick_engine_from_settlement(settlements['town_1'])},
        settlement_links=(),
        region_definitions={'river_trade': build_phase3_regions()['river_trade']},
        continent_definitions={continent.continent_id: continent},
        initial_settlement_id='town_1',
    )

    reset_snapshot = reset_world_to_seed(custom_engine)

    assert reset_snapshot.active_settlement_id == 'town_1'
    assert set(reset_snapshot.settlement_states) == {'town_1'}
    assert reset_snapshot.settlement_state.player_location == '광장'
    assert reset_snapshot.chronicle_archive.entries == ()


def test_cli_load_returns_snapshot_without_hidden_function_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(world_engine_module, 'SAVE_DIR', tmp_path / 'saves')
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.travel('village_2'))
    save_world_state_to_slot(snapshot, 2)
    inputs = deque(['load 2'])
    outputs: list[str] = []

    result = prompt_player_action(
        [location for location in snapshot.settlement_definition.locations if location != '집'],
        list(snapshot.settlement_definition.npc_ids),
        current_location=snapshot.settlement_state.player_location,
        travel_targets=['village_1'],
        history_snapshot=snapshot,
        input_func=lambda _: inputs.popleft(),
        output_func=outputs.append,
        load_func=lambda slot: load_world_state_from_slot(
            slot,
            settlement_definitions=world_engine.settlement_definitions,
            settlement_links=world_engine.settlement_links,
            region_definitions=world_engine.region_definitions,
            continent_definitions=world_engine.continent_definitions,
        ),
        reset_func=lambda: reset_world_to_seed(world_engine),
        save_func=lambda slot: save_world_state_to_slot(snapshot, slot),
    )

    assert result.active_settlement_id == snapshot.active_settlement_id
    assert result.settlement_state.tick == snapshot.settlement_state.tick
    assert result.settlement_state.player_location == snapshot.settlement_state.player_location
    assert len(result.chronicle_archive.entries) == len(snapshot.chronicle_archive.entries)
    assert not hasattr(prompt_player_action, '_last_snapshot')
    assert any('world load complete' in line for line in outputs)


def test_reset_chooses_same_initial_active_settlement_for_same_engine_seed() -> None:
    world_engine = build_world_engine()

    first_reset = reset_world_to_seed(world_engine)
    second_reset = reset_world_to_seed(world_engine)

    assert first_reset.active_settlement_id == 'village_1'
    assert second_reset.active_settlement_id == 'village_1'
    assert first_reset.active_settlement_id == second_reset.active_settlement_id


def test_slot_save_and_load_restore_runtime_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(world_engine_module, 'SAVE_DIR', tmp_path / 'saves')
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    metadata = save_world_state_to_slot(snapshot, 1)
    loaded_snapshot = load_world_state_from_slot(
        1,
        settlement_definitions=world_engine.settlement_definitions,
        settlement_links=world_engine.settlement_links,
        region_definitions=world_engine.region_definitions,
        continent_definitions=world_engine.continent_definitions,
    )

    assert metadata['slot'] == 1
    assert (tmp_path / 'saves' / 'slot_1.json').exists()
    assert save_world_state(loaded_snapshot) == save_world_state(snapshot)


def test_recent_save_slots_are_listed_in_recent_order(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(world_engine_module, 'SAVE_DIR', tmp_path / 'saves')
    snapshot = create_default_world_snapshot()

    first = save_world_state_to_slot(snapshot, 1)
    second = save_world_state_to_slot(snapshot, 2)
    recent = world_engine_module.list_recent_save_slots()

    assert [item['slot'] for item in recent][:2] == [2, 1]
    assert recent[0]['saved_at'] >= recent[1]['saved_at']
    assert first['active_settlement_id'] == second['active_settlement_id']
