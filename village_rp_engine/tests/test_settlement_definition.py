from __future__ import annotations

from village_rp_engine.domain.settlement_data import (
    build_phase1_settlement,
    build_phase2_settlement_links,
    build_phase2_settlements,
    build_phase3_region_states,
    build_phase3_regions,
)


def test_settlement_definition_wraps_existing_seed_data() -> None:
    settlement = build_phase1_settlement()

    assert settlement.settlement_id == 'village_1'
    assert settlement.region_id == 'north_fields'
    assert 'farmer' in settlement.npc_ids
    assert 'ethan' in settlement.npc_ids
    assert '광장' in settlement.locations
    assert 'farmer' in settlement.schedules
    assert any(event.event_id == 'argument_at_tavern' for event in settlement.event_definitions)
    assert settlement.economy_profile.values == {'grain': 80, 'iron': 10}
    assert settlement.security.value == 60
    assert settlement.stress_default == 20
    assert settlement.flavor.title == '회색언덕 마을'


def test_phase2_settlement_registry_contains_three_distinct_settlements() -> None:
    settlements = build_phase2_settlements()

    assert {'village_1', 'village_2', 'town_1'} == set(settlements)
    assert settlements['village_1'].economy_profile.values != settlements['village_2'].economy_profile.values
    assert settlements['village_2'].npc_ids != settlements['town_1'].npc_ids
    assert settlements['town_1'].locations != settlements['village_1'].locations


def test_settlements_expose_distinct_flavor_and_facilities() -> None:
    settlements = build_phase2_settlements()

    village_1_facilities = {facility.facility_id for facility in settlements['village_1'].facilities}
    village_2_facilities = {facility.facility_id for facility in settlements['village_2'].facilities}
    town_1_facilities = {facility.facility_id for facility in settlements['town_1'].facilities}

    assert 'market' not in village_1_facilities
    assert 'clinic' in village_2_facilities
    assert 'market' in town_1_facilities
    assert settlements['village_1'].flavor.rumor_bias == ('local', 'gossip', 'daily_life')
    assert settlements['village_2'].flavor.rumor_bias == ('refugee', 'traveler', 'recovery')
    assert settlements['town_1'].flavor.rumor_bias == ('trade', 'merchant', 'politics')


def test_phase2_settlement_links_exist_for_travel_and_rumor_flow() -> None:
    links = build_phase2_settlement_links()

    assert any(link.from_settlement_id == 'village_1' and link.to_settlement_id == 'village_2' for link in links)
    assert any(link.from_settlement_id == 'town_1' and link.to_settlement_id == 'village_2' for link in links)


def test_phase3_region_registry_is_seed_consistent() -> None:
    settlements = build_phase2_settlements()
    regions = build_phase3_regions()
    region_states = build_phase3_region_states()

    assert {'north_fields', 'river_trade'} == set(regions)
    assert set(region_states) == set(regions)
    assert settlements['village_1'].region_id == 'north_fields'
    assert settlements['village_2'].region_id == 'north_fields'
    assert settlements['town_1'].region_id == 'river_trade'
    assert set(regions['north_fields'].settlement_ids) == {'village_1', 'village_2'}
