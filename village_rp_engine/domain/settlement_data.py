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
    FacilityDefinition,
    RegionDefinition,
    RegionRuntimeState,
    SecurityState,
    SettlementDefinition,
    SettlementFlavor,
    SettlementLink,
)


PHASE1_SETTLEMENT_ID = 'village_1'
PHASE1_ECONOMY_PROFILE = {'grain': 80, 'iron': 10}
PHASE1_SECURITY = 60
PHASE1_STRESS = 20


def build_facilities(
    *,
    has_tavern: bool,
    has_square: bool = True,
    has_back_alley: bool = True,
    has_clinic: bool = False,
    has_market: bool = False,
) -> tuple[FacilityDefinition, ...]:
    facilities: list[FacilityDefinition] = []
    if has_square:
        facilities.append(
            FacilityDefinition(
                facility_id='square',
                label='광장',
                facility_type='public',
                target_location='광장',
            )
        )
    if has_tavern:
        facilities.append(
            FacilityDefinition(
                facility_id='tavern',
                label='술집',
                facility_type='rumor',
                target_location='술집',
            )
        )
    if has_back_alley:
        facilities.append(
            FacilityDefinition(
                facility_id='back_alley',
                label='뒷골목',
                facility_type='hidden_rumor',
                target_location='뒷골목',
            )
        )
    if has_clinic:
        facilities.append(
            FacilityDefinition(
                facility_id='clinic',
                label='치료소',
                facility_type='recovery',
            )
        )
    if has_market:
        facilities.append(
            FacilityDefinition(
                facility_id='market',
                label='시장',
                facility_type='trade',
                target_location='시장',
            )
        )
    facilities.extend(
        (
            FacilityDefinition('archive', '기록관', 'chronicle', target_location='기록관'),
            FacilityDefinition('base', '거점', 'safehouse', target_location='거점'),
            FacilityDefinition('outside', '도시 밖으로', 'travel'),
        )
    )
    return tuple(facilities)


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
        facilities=build_facilities(has_tavern=True),
        flavor=SettlementFlavor(
            title='회색언덕 마을',
            summary='작고 조용한 시골 마을이다. 에단이 너를 구해 들인 뒤, 사람들의 소문과 기록이 천천히 쌓이고 있다.',
            rumor_bias=('local', 'gossip', 'daily_life'),
            rumor_intro='회색언덕 사람들은 이런 이야기를 주고받는다.',
            archive_intro='회색언덕 기록관에는 사람들이 남긴 흔적과 네가 모은 기록이 함께 쌓인다.',
            npc_bias=('주민', '농부', '마을 청년', '경비병'),
        ),
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
            outcome_text='강가마을 광장에서 농부가 창고 사정을 두고 아침 이야기를 나눴다.',
            rumor_text='강가마을 광장에서 창고 사정 이야기가 돌았다는 소문이 퍼졌다.',
        ),
        replace(
            event_lookup['late_night_cleanup'],
            probability=0.6,
            outcome_text='강가마을 여관주인이 늦은 밤 창고 손님 이야기까지 정리했다.',
            rumor_text='강가마을 술집에서 늦은 밤 손님 이야기가 돌았다는 말이 퍼졌다.',
        ),
    )
    town_1_events = (
        replace(
            event_lookup['late_night_cleanup'],
            probability=0.8,
            outcome_text='시장마을 여관주인이 시장 손님이 빠진 뒤 술집을 정리했다.',
            rumor_text='시장마을 손님들이 밤늦게 술집에 들렀다는 말이 돌았다.',
        ),
    )

    return {
        base.settlement_id: base,
        'village_2': SettlementDefinition(
            settlement_id='village_2',
            region_id='north_fields',
            npc_ids=('farmer', 'innkeeper', 'village_elder', 'guard_captain'),
            locations=('광장', '술집', '뒷골목', '기록관', '거점', '창고', '집'),
            schedules=village_2_schedules,
            event_definitions=village_2_events,
            economy_profile=EconomyProfile(values={'grain': 110, 'iron': 4}),
            security=SecurityState(value=55),
            stress_default=25,
            rumor_tone='granary',
            facilities=build_facilities(has_tavern=True, has_clinic=True),
            flavor=SettlementFlavor(
                title='여행자와 피난민이 드나드는 마을',
                summary='상처를 추스르는 이들과 길손들의 발걸음이 자주 머문다.',
                rumor_bias=('refugee', 'traveler', 'recovery'),
                rumor_intro='길손들과 머문 이들이 남긴 이야기가 이어진다.',
                archive_intro='여행자들이 남긴 기록과 회복의 흔적이 쌓이는 곳이다.',
                npc_bias=('의사', '약초상', '여행자', '피난민'),
            ),
        ),
        'town_1': SettlementDefinition(
            settlement_id='town_1',
            region_id='river_trade',
            npc_ids=('blacksmith', 'innkeeper', 'village_elder', 'guard_captain'),
            locations=('광장', '대장간', '술집', '뒷골목', '기록관', '거점', '시장', '집'),
            schedules=town_1_schedules,
            event_definitions=town_1_events,
            economy_profile=EconomyProfile(values={'grain': 60, 'iron': 55, 'trade': 40}),
            security=SecurityState(value=72),
            stress_default=18,
            rumor_tone='market',
            facilities=build_facilities(has_tavern=True, has_market=True),
            flavor=SettlementFlavor(
                title='상업 중심 소도시',
                summary='거래와 방문객, 계약 이야기가 하루 종일 오가는 곳이다.',
                rumor_bias=('trade', 'merchant', 'politics'),
                rumor_intro='장터와 여관에서는 이런 말들이 오간다.',
                archive_intro='도시 기록관에는 거래와 분쟁의 흔적이 차곡차곡 남아 있다.',
                npc_bias=('상인', '관리', '길드원', '방문객'),
            ),
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
