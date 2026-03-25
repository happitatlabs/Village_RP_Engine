from __future__ import annotations

from village_rp_engine.core.mode_controller import build_world_engine, create_default_world_snapshot
from village_rp_engine.core.world_engine import produce_continent_influences
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.phase1_world import ContinentRuntimeState
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.models.rumor import Rumor


def test_regions_belong_to_continent() -> None:
    snapshot = create_default_world_snapshot()

    for region_id, region_definition in snapshot.region_definitions.items():
        assert region_definition.continent_id in snapshot.continent_definitions
        assert region_id in snapshot.continent_definitions[region_definition.continent_id].region_ids


def test_world_snapshot_supports_continent_registry() -> None:
    snapshot = create_default_world_snapshot()

    assert snapshot.continent_definitions
    assert snapshot.continent_states
    assert 'continent_1' in snapshot.continent_definitions


def test_continent_produces_influence_for_regions() -> None:
    snapshot = create_default_world_snapshot()

    influences = produce_continent_influences(snapshot)

    assert {'north_fields', 'river_trade'}.issubset(influences)
    assert influences['north_fields']['security_risk_delta'] >= 0
    assert influences['river_trade']['rumor_density_delta'] >= 0


def test_continent_influence_updates_region_state() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    before = snapshot.region_states['north_fields']

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    after = snapshot.region_states['north_fields']

    assert after.security_risk > before.security_risk
    assert after.trade_flow < before.trade_flow
    assert after.rumor_density > before.rumor_density


def test_influence_chain_continent_to_settlement() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    before_security = snapshot.settlement_states['village_1'].security
    before_stress = snapshot.settlement_states['village_1'].stress

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    assert snapshot.region_states['north_fields'].security_risk >= 2
    assert snapshot.settlement_states['village_1'].security < before_security
    assert snapshot.settlement_states['village_1'].stress > before_stress


def test_continent_runtime_state_evolves_from_previous_state() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = snapshot.__class__(
        settlement_definitions=snapshot.settlement_definitions,
        settlement_states=snapshot.settlement_states,
        active_settlement_id=snapshot.active_settlement_id,
        recently_visited_ids=snapshot.recently_visited_ids,
        presentation_state=snapshot.presentation_state,
        simulation_depth=snapshot.simulation_depth,
        pending_influences=snapshot.pending_influences,
        settlement_links=snapshot.settlement_links,
        propagated_rumor_keys=snapshot.propagated_rumor_keys,
        region_definitions=snapshot.region_definitions,
        region_states=snapshot.region_states,
        continent_definitions=snapshot.continent_definitions,
        continent_states={
            **snapshot.continent_states,
            'continent_1': ContinentRuntimeState(
                continent_id='continent_1',
                global_tension=4,
                trade_pressure=4,
                migration_pressure=3,
                rumor_noise=3,
                stability=6,
            ),
        },
    )

    next_snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    next_state = next_snapshot.continent_states['continent_1']

    assert next_state != snapshot.continent_states['continent_1']
    assert next_state.global_tension >= 2
    assert next_state.trade_pressure >= 2


def test_chronicle_includes_continent_summary() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    assert any(entry.entry_type == 'continent_summary' for entry in snapshot.presentation_state.chronicle_entries)
    assert any('continent_1' in entry.text for entry in snapshot.presentation_state.chronicle_entries)


def test_continent_chronicle_uses_actual_world_time() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    continent_entries = [entry for entry in snapshot.presentation_state.chronicle_entries if entry.entry_type == 'continent_summary']

    assert continent_entries
    assert all(entry.day == snapshot.settlement_state.day for entry in continent_entries)
    assert all(entry.tick == snapshot.settlement_state.tick for entry in continent_entries)


def test_phase3_behavior_still_valid() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot.settlement_states['village_1'].rumor_log.append(
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

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.travel('village_2'))

    assert snapshot.active_settlement_id == 'village_2'
    assert snapshot.settlement_states['village_1'].player_location is None
    assert snapshot.settlement_states['village_2'].player_location is not None
    assert snapshot.settlement_states['town_1'].visible_scenes == []
    assert any(rumor.is_remote for rumor in snapshot.settlement_states['village_2'].rumor_log)
