from __future__ import annotations

from village_rp_engine.domain.settlement_data import build_phase1_settlement


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
