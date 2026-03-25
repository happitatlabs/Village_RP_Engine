from __future__ import annotations

from village_rp_engine.core.mode_controller import build_world_engine, create_default_world_snapshot
from village_rp_engine.core.world_engine import produce_region_influences
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.phase1_world import RegionRuntimeState
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.models.rumor import Rumor


def test_settlements_belong_to_regions() -> None:
    snapshot = create_default_world_snapshot()

    for settlement_id, settlement_definition in snapshot.settlement_definitions.items():
        assert settlement_definition.region_id in snapshot.region_definitions
        assert settlement_id in snapshot.region_definitions[settlement_definition.region_id].settlement_ids


def test_world_snapshot_supports_region_registry() -> None:
    snapshot = create_default_world_snapshot()

    assert snapshot.region_definitions
    assert snapshot.region_states
    assert {'north_fields', 'river_trade'}.issubset(snapshot.region_definitions)


def test_region_produces_influence_packets_for_member_settlements() -> None:
    snapshot = create_default_world_snapshot()

    packets = produce_region_influences(snapshot)
    packet_targets = {packet.target_settlement_id for packet in packets}

    assert {'village_1', 'village_2', 'town_1'}.issubset(packet_targets)
    assert all(packet.source_layer.startswith('region:') for packet in packets)


def test_region_influence_applies_to_settlement_state() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    before = snapshot.settlement_states['village_1']
    before_security = before.security
    before_stress = before.stress
    before_grain = before.economy_profile['grain']

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    after = snapshot.settlement_states['village_1']

    assert after.security <= before_security
    assert after.stress > before_stress
    assert after.economy_profile['grain'] > before_grain


def test_recent_and_unvisited_settlements_receive_region_influence() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    before_village_1_stress = snapshot.settlement_states['village_1'].stress
    before_town_1_trade = snapshot.settlement_states['town_1'].economy_profile['trade']

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.travel('village_2'))

    assert snapshot.settlement_states['village_1'].stress > before_village_1_stress
    assert snapshot.settlement_states['town_1'].economy_profile['trade'] > before_town_1_trade


def test_region_runtime_state_evolves_from_previous_state() -> None:
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
        region_states={
            **snapshot.region_states,
            'north_fields': RegionRuntimeState(
                region_id='north_fields',
                security_risk=4,
                trade_flow=5,
                rumor_density=3,
                stress_modifier=2,
                economy_modifier=dict(snapshot.region_states['north_fields'].economy_modifier),
            ),
        },
        continent_definitions=snapshot.continent_definitions,
        continent_states=snapshot.continent_states,
    )

    next_snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    next_state = next_snapshot.region_states['north_fields']

    assert next_state.security_risk >= 3
    assert next_state.trade_flow > snapshot.region_definitions['north_fields'].trade_flow
    assert next_state.rumor_density >= 2
    assert next_state.stress_modifier >= 1


def test_region_summary_appears_in_chronicle() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    assert any(entry.entry_type == 'region_summary' for entry in snapshot.presentation_state.chronicle_entries)
    assert any('north_fields' in entry.text or 'river_trade' in entry.text for entry in snapshot.presentation_state.chronicle_entries)


def test_region_chronicle_uses_actual_world_time() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    region_entries = [entry for entry in snapshot.presentation_state.chronicle_entries if entry.entry_type == 'region_summary']

    assert region_entries
    assert all(entry.day == snapshot.settlement_state.day for entry in region_entries)
    assert all(entry.tick == snapshot.settlement_state.tick for entry in region_entries)


def test_phase2_travel_and_rumor_behavior_still_hold_under_regions() -> None:
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
