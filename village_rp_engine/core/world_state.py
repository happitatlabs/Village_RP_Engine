from __future__ import annotations

from dataclasses import dataclass, field

from village_rp_engine.config import (
    DEFAULT_PLAYER_LOCATION,
    MEDIATE_TAVERN_CONFLICT_QUEST_ID,
    PLAYER_RELATIONSHIP_NPC_IDS,
    TIME_PHASES,
)
from village_rp_engine.models.dialogue import Dialogue
from village_rp_engine.models.event import TriggeredEvent
from village_rp_engine.models.npc_state import NPCRecentState
from village_rp_engine.models.player_notice import PlayerNotice
from village_rp_engine.models.rumor import Rumor
from village_rp_engine.models.scene import Scene


def build_initial_player_relationships() -> dict[str, int]:
    return {npc_id: 0 for npc_id in PLAYER_RELATIONSHIP_NPC_IDS}


def _get_phase1_settlement_definition():
    from village_rp_engine.domain.settlement_data import build_phase1_settlement

    return build_phase1_settlement()


def _default_settlement_id() -> str:
    return _get_phase1_settlement_definition().settlement_id


def _default_security() -> int:
    settlement = _get_phase1_settlement_definition()
    return getattr(settlement.security, 'base_value', settlement.security.value)


def _default_stress() -> int:
    return _get_phase1_settlement_definition().stress_default


def build_default_economy_profile() -> dict[str, int | float]:
    return dict(_get_phase1_settlement_definition().economy_profile.values)


# Phase 1 rule: WorldState is the settlement-local source of truth.
@dataclass
class WorldState:
    tick: int
    day: int
    time_phase: str
    settlement_id: str = field(default_factory=_default_settlement_id)
    security: int = field(default_factory=_default_security)
    stress: int = field(default_factory=_default_stress)
    economy_profile: dict[str, int | float] = field(default_factory=build_default_economy_profile)
    npc_locations: dict[str, str] = field(default_factory=dict)
    previous_npc_locations: dict[str, str] = field(default_factory=dict)
    player_location: str | None = DEFAULT_PLAYER_LOCATION
    previous_player_location: str | None = DEFAULT_PLAYER_LOCATION
    triggered_events: list[TriggeredEvent] = field(default_factory=list)
    visible_scenes: list[Scene] = field(default_factory=list)
    dialogues: list[Dialogue] = field(default_factory=list)
    rumor_log: list[Rumor] = field(default_factory=list)
    world_log: list[str] = field(default_factory=list)
    relationships: dict[tuple[str, str], int] = field(default_factory=dict)
    player_relationships: dict[str, int] = field(default_factory=build_initial_player_relationships)
    quest_status: dict[str, str] = field(default_factory=lambda: {MEDIATE_TAVERN_CONFLICT_QUEST_ID: 'not_started'})
    quest_contacts: dict[str, set[str]] = field(default_factory=lambda: {MEDIATE_TAVERN_CONFLICT_QUEST_ID: set()})
    npc_recent_states: dict[str, list[NPCRecentState]] = field(default_factory=dict)
    player_notices: list[PlayerNotice] = field(default_factory=list)
    locked_npc_ids_for_tick: set[str] = field(default_factory=set)
    event_last_trigger_tick: dict[str, int] = field(default_factory=dict)
    rumor_history_keys: set[str] = field(default_factory=set)
    recent_scene_event_ids: set[str] = field(default_factory=set)


def create_initial_world_state(player_location: str | None = DEFAULT_PLAYER_LOCATION) -> WorldState:
    return WorldState(
        tick=0,
        day=1,
        time_phase=TIME_PHASES[0],
        npc_locations={},
        previous_npc_locations={},
        player_location=player_location,
        previous_player_location=player_location,
    )
