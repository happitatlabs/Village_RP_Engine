from __future__ import annotations

from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.location_data import build_locations
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules
from village_rp_engine.models.npc import NPC
from village_rp_engine.models.phase1_world import EconomyProfile, SecurityState, SettlementDefinition


PHASE1_SETTLEMENT_ID = 'village_1'
PHASE1_ECONOMY_PROFILE = {'grain': 80, 'iron': 10}
PHASE1_SECURITY = 60
PHASE1_STRESS = 20


def build_phase1_settlement() -> SettlementDefinition:
    npcs = build_npcs()
    return SettlementDefinition(
        settlement_id=PHASE1_SETTLEMENT_ID,
        npc_ids=tuple(npc.npc_id for npc in npcs),
        locations=tuple(build_locations()),
        schedules=build_schedules(),
        event_definitions=tuple(build_event_definitions()),
        economy_profile=EconomyProfile(values=dict(PHASE1_ECONOMY_PROFILE)),
        security=SecurityState(value=PHASE1_SECURITY),
        stress_default=PHASE1_STRESS,
    )


def build_npcs_for_settlement(settlement: SettlementDefinition) -> list[NPC]:
    npc_lookup = {npc.npc_id: npc for npc in build_npcs()}
    return [npc_lookup[npc_id] for npc_id in settlement.npc_ids]


def get_phase1_npc_ids() -> list[str]:
    return list(build_phase1_settlement().npc_ids)


def get_phase1_npc_name_map() -> dict[str, str]:
    settlement = build_phase1_settlement()
    return {npc.npc_id: npc.name for npc in build_npcs_for_settlement(settlement)}
