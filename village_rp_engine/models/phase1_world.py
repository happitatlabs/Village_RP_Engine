from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.event import EventDefinition


class SimulationDepth(IntEnum):
    UNVISITED = 0
    RECENT = 1
    ACTIVE = 2


@dataclass(frozen=True)
class EconomyProfile:
    values: dict[str, int | float]


@dataclass(frozen=True)
class SecurityState:
    value: int


@dataclass(frozen=True)
class InfluencePacket:
    source_layer: str
    target_settlement_id: str
    economy_delta: dict[str, int | float] = field(default_factory=dict)
    security_delta: int = 0
    stress_delta: int = 0
    rumor_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class SettlementDefinition:
    settlement_id: str
    npc_ids: tuple[str, ...]
    locations: tuple[str, ...]
    schedules: dict[str, dict[str, str]]
    event_definitions: tuple[EventDefinition, ...]
    economy_profile: EconomyProfile
    security: SecurityState
    stress_default: int


@dataclass(frozen=True)
class SettlementRuntimeState:
    settlement_id: str
    security: int
    stress: int
    economy_profile: dict[str, int | float]


@dataclass(frozen=True)
class ChronicleEntry:
    entry_type: str
    source_id: str | None
    day: int
    tick: int
    text: str


@dataclass(frozen=True)
class PresentationDialogue:
    speaker_id: str
    speaker_name: str
    text: str


@dataclass(frozen=True)
class PresentationEventSummary:
    event_id: str
    outcome_text: str


@dataclass(frozen=True)
class PresentationNPC:
    npc_id: str
    name: str


@dataclass(frozen=True)
class PresentationState:
    visible_scenes: tuple[str, ...] = ()
    dialogues: tuple[PresentationDialogue, ...] = ()
    triggered_event_summaries: tuple[PresentationEventSummary, ...] = ()
    rumor_lines: tuple[str, ...] = ()
    relationship_lines: tuple[str, ...] = ()
    player_relationship_lines: tuple[str, ...] = ()
    quest_lines: tuple[str, ...] = ()
    world_log_lines: tuple[str, ...] = ()
    chronicle_entries: tuple[ChronicleEntry, ...] = ()
    present_npcs: tuple[PresentationNPC, ...] = ()
    npc_status_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorldSnapshot:
    settlement_state: WorldState
    presentation_state: PresentationState
    simulation_depth: SimulationDepth
    pending_influences: tuple[InfluencePacket, ...] = ()


SettlementState = WorldState
