from __future__ import annotations

from dataclasses import replace

from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.location_data import build_locations
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules
from village_rp_engine.models.npc import NPC
from village_rp_engine.models.phase1_world import (
    ContinentDefinition,
    ContinentRuntimeState,
    EconomyProfile,
    RegionDefinition,
    RegionRuntimeState,
    SecurityState,
    SettlementDefinition,
    SettlementLink,
)


PHASE1_SETTLEMENT_ID = 'village_1'
PHASE1_ECONOMY_PROFILE = {'grain': 80, 'iron': 10}
PHASE1_SECURITY = 60
PHASE1_STRESS = 20


def build_phase1_settlement() -> SettlementDefinition:
    npcs = build_npcs()
    return SettlementDefinition(
        settlement_id=PHASE1_SETTLEMENT_ID,
        region_id='north_fields',
        npc_ids=tuple(npc.npc_id for npc in npcs),
        locations=tuple(build_locations()),
        schedules=build_schedules(),
        event_definitions=tuple(build_event_definitions()),
        economy_profile=EconomyProfile(values=dict(PHASE1_ECONOMY_PROFILE)),
        security=SecurityState(value=PHASE1_SECURITY),
        stress_default=PHASE1_STRESS,
        rumor_tone='village',
    )


def build_phase2_settlements() -> dict[str, SettlementDefinition]:
    base = build_phase1_settlement()
    event_lookup = {event.event_id: event for event in build_event_definitions()}

    village_2_schedules = {
        'farmer': {'아침': '광장', '낮': '창고', '저녁': '술집', '밤': '집', '새벽': '집'},
        'innkeeper': {'아침': '술집', '낮': '술집', '저녁': '술집', '밤': '술집', '새벽': '술집'},
        'village_elder': {'아침': '광장', '낮': '창고', '저녁': '술집', '밤': '집', '새벽': '집'},
        'guard_captain': {'아침': '광장', '낮': '창고', '저녁': '술집', '밤': '광장', '새벽': '광장'},
    }
    town_1_schedules = {
        'blacksmith': {'아침': '대장간', '낮': '대장간', '저녁': '시장', '밤': '집', '새벽': '집'},
        'innkeeper': {'아침': '술집', '낮': '술집', '저녁': '술집', '밤': '술집', '새벽': '술집'},
        'village_elder': {'아침': '광장', '낮': '시장', '저녁': '술집', '밤': '집', '새벽': '집'},
        'guard_captain': {'아침': '광장', '낮': '시장', '저녁': '술집', '밤': '광장', '새벽': '광장'},
    }

    village_2_events = (
        replace(
            event_lookup['morning_chat_square'],
            probability=0.7,
            outcome_text='village_2의 광장에서 농부가 창고 사정을 두고 아침 이야기를 나눴다.',
            rumor_text='village_2 광장에서 창고 사정 이야기가 돌았다는 소문이 퍼졌다.',
        ),
        replace(
            event_lookup['late_night_cleanup'],
            probability=0.6,
            outcome_text='village_2의 여관주인이 늦은 밤 창고 손님 이야기까지 정리했다.',
            rumor_text='village_2 술집에서 늦은 밤 손님 이야기가 돌았다는 말이 퍼졌다.',
        ),
    )
    town_1_events = (
        replace(
            event_lookup['late_night_cleanup'],
            probability=0.8,
            outcome_text='town_1의 여관주인이 시장 손님이 빠진 뒤 술집을 정리했다.',
            rumor_text='town_1 시장 손님들이 밤늦게 술집에 들렀다는 말이 돌았다.',
        ),
    )

    return {
        base.settlement_id: base,
        'village_2': SettlementDefinition(
            settlement_id='village_2',
            region_id='north_fields',
            npc_ids=('farmer', 'innkeeper', 'village_elder', 'guard_captain'),
            locations=('광장', '술집', '창고', '집'),
            schedules=village_2_schedules,
            event_definitions=village_2_events,
            economy_profile=EconomyProfile(values={'grain': 110, 'iron': 4}),
            security=SecurityState(value=55),
            stress_default=25,
            rumor_tone='granary',
        ),
        'town_1': SettlementDefinition(
            settlement_id='town_1',
            region_id='river_trade',
            npc_ids=('blacksmith', 'innkeeper', 'village_elder', 'guard_captain'),
            locations=('광장', '대장간', '술집', '시장', '집'),
            schedules=town_1_schedules,
            event_definitions=town_1_events,
            economy_profile=EconomyProfile(values={'grain': 60, 'iron': 55, 'trade': 40}),
            security=SecurityState(value=72),
            stress_default=18,
            rumor_tone='market',
        ),
    }


def build_phase2_settlement_links() -> tuple[SettlementLink, ...]:
    return (
        SettlementLink('village_1', 'village_2', 'road', 1, 1, 1),
        SettlementLink('village_2', 'village_1', 'road', 1, 1, 1),
        SettlementLink('village_2', 'town_1', 'road', 2, 2, 2),
        SettlementLink('town_1', 'village_2', 'road', 2, 2, 2),
        SettlementLink('village_1', 'town_1', 'road', 3, 2, 3),
        SettlementLink('town_1', 'village_1', 'road', 3, 2, 3),
    )


def build_phase3_regions() -> dict[str, RegionDefinition]:
    return {
        'north_fields': RegionDefinition(
            region_id='north_fields',
            continent_id='continent_1',
            name='North Fields',
            settlement_ids=('village_1', 'village_2'),
            security_risk=1,
            trade_flow=1,
            rumor_density=1,
            stress_modifier=1,
            economy_modifier={'grain': 2},
        ),
        'river_trade': RegionDefinition(
            region_id='river_trade',
            continent_id='continent_1',
            name='River Trade',
            settlement_ids=('town_1',),
            security_risk=0,
            trade_flow=3,
            rumor_density=2,
            stress_modifier=0,
            economy_modifier={'trade': 2, 'iron': 1},
        ),
    }


def build_phase3_region_states() -> dict[str, RegionRuntimeState]:
    return {
        region_id: RegionRuntimeState(
            region_id=region.region_id,
            security_risk=region.security_risk,
            trade_flow=region.trade_flow,
            rumor_density=region.rumor_density,
            stress_modifier=region.stress_modifier,
            economy_modifier=dict(region.economy_modifier),
        )
        for region_id, region in build_phase3_regions().items()
    }


def build_phase4_continent() -> ContinentDefinition:
    return ContinentDefinition(
        continent_id='continent_1',
        name='Continental Belt',
        region_ids=('north_fields', 'river_trade'),
        global_tension=2,
        trade_pressure=2,
        migration_pressure=1,
        rumor_noise=2,
        stability=4,
    )


def build_phase4_continent_states() -> dict[str, ContinentRuntimeState]:
    continent = build_phase4_continent()
    return {
        continent.continent_id: ContinentRuntimeState(
            continent_id=continent.continent_id,
            global_tension=continent.global_tension,
            trade_pressure=continent.trade_pressure,
            migration_pressure=continent.migration_pressure,
            rumor_noise=continent.rumor_noise,
            stability=continent.stability,
        )
    }


def build_npcs_for_settlement(settlement: SettlementDefinition) -> list[NPC]:
    npc_lookup = {npc.npc_id: npc for npc in build_npcs()}
    return [npc_lookup[npc_id] for npc_id in settlement.npc_ids]


def get_phase1_npc_ids() -> list[str]:
    return list(build_phase1_settlement().npc_ids)


def get_phase1_npc_name_map() -> dict[str, str]:
    settlement = build_phase1_settlement()
    return {npc.npc_id: npc.name for npc in build_npcs_for_settlement(settlement)}


def get_phase2_npc_ids(settlement_id: str) -> list[str]:
    return list(build_phase2_settlements()[settlement_id].npc_ids)


def get_phase2_npc_name_map() -> dict[str, str]:
    npc_lookup = {npc.npc_id: npc.name for npc in build_npcs()}
    ids = {
        npc_id
        for settlement in build_phase2_settlements().values()
        for npc_id in settlement.npc_ids
    }
    return {npc_id: npc_lookup[npc_id] for npc_id in sorted(ids)}
