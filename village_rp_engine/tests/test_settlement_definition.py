from __future__ import annotations

from village_rp_engine.domain.settlement_data import build_phase1_settlement, build_phase2_settlement_links, build_phase2_settlements


def test_settlement_definition_wraps_existing_seed_data() -> None:
    settlement = build_phase1_settlement()

    assert settlement.settlement_id == 'village_1'
    assert 'farmer' in settlement.npc_ids
    assert '광장' in settlement.locations
    assert 'farmer' in settlement.schedules
    assert any(event.event_id == 'argument_at_tavern' for event in settlement.event_definitions)
    assert settlement.economy_profile.values == {'grain': 80, 'iron': 10}
    assert settlement.security.value == 60
    assert settlement.stress_default == 20


def test_phase2_settlement_registry_contains_three_distinct_settlements() -> None:
    settlements = build_phase2_settlements()

    assert {'village_1', 'village_2', 'town_1'} == set(settlements)
    assert settlements['village_1'].economy_profile.values != settlements['village_2'].economy_profile.values
    assert settlements['village_2'].npc_ids != settlements['town_1'].npc_ids
    assert settlements['town_1'].locations != settlements['village_1'].locations


def test_phase2_settlement_links_exist_for_travel_and_rumor_flow() -> None:
    links = build_phase2_settlement_links()

    assert any(link.from_settlement_id == 'village_1' and link.to_settlement_id == 'village_2' for link in links)
    assert any(link.from_settlement_id == 'town_1' and link.to_settlement_id == 'village_2' for link in links)
