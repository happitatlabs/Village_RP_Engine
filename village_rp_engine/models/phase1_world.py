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

    @property
    def base_value(self) -> int:
        return self.value


@dataclass(frozen=True)
class InfluencePacket:
    source_layer: str
    target_settlement_id: str
    economy_delta: dict[str, int | float] = field(default_factory=dict)
    security_delta: int = 0
    stress_delta: int = 0
    rumor_tags: tuple[str, ...] = ()
    scope: str = 'settlement'
    delay_ticks: int = 0
    chronicle_reference: str | None = None
    choice_id: str | None = None
    player_driven: bool = False
    special_npc_signal: int = 0


@dataclass(frozen=True)
class FacilityDefinition:
    facility_id: str
    label: str
    facility_type: str
    enabled: bool = True
    target_location: str | None = None


@dataclass(frozen=True)
class SettlementFlavor:
    title: str
    summary: str
    rumor_bias: tuple[str, ...] = ()
    rumor_intro: str = ''
    archive_intro: str = ''
    npc_bias: tuple[str, ...] = ()


@dataclass(frozen=True)
class SettlementDefinition:
    settlement_id: str
    region_id: str
    npc_ids: tuple[str, ...]
    locations: tuple[str, ...]
    schedules: dict[str, dict[str, str]]
    event_definitions: tuple[EventDefinition, ...]
    economy_profile: EconomyProfile
    security: SecurityState
    stress_default: int
    rumor_tone: str = 'neutral'
    facilities: tuple[FacilityDefinition, ...] = ()
    flavor: SettlementFlavor = field(default_factory=lambda: SettlementFlavor(title='', summary=''))


@dataclass(frozen=True)
class SettlementRuntimeState:
    settlement_id: str
    security: int
    stress: int
    economy_profile: dict[str, int | float]


@dataclass(frozen=True)
class RegionDefinition:
    region_id: str
    continent_id: str
    name: str
    settlement_ids: tuple[str, ...]
    security_risk: int
    trade_flow: int
    rumor_density: int
    stress_modifier: int
    economy_modifier: dict[str, int | float] = field(default_factory=dict)


@dataclass(frozen=True)
class RegionRuntimeState:
    region_id: str
    security_risk: int
    trade_flow: int
    rumor_density: int
    stress_modifier: int
    economy_modifier: dict[str, int | float] = field(default_factory=dict)


@dataclass(frozen=True)
class ContinentDefinition:
    continent_id: str
    name: str
    region_ids: tuple[str, ...]
    global_tension: int
    trade_pressure: int
    migration_pressure: int
    rumor_noise: int
    stability: int


@dataclass(frozen=True)
class ContinentRuntimeState:
    continent_id: str
    global_tension: int
    trade_pressure: int
    migration_pressure: int
    rumor_noise: int
    stability: int


@dataclass(frozen=True)
class SettlementLink:
    from_settlement_id: str
    to_settlement_id: str
    link_type: str
    distance: int
    rumor_speed: int
    travel_cost: int


@dataclass(frozen=True)
class ChronicleEntry:
    entry_type: str
    source_id: str | None
    day: int
    tick: int
    text: str
    settlement_id: str | None = None
    region_id: str | None = None
    continent_id: str | None = None
    layer: str = 'settlement'
    category: str = 'STATE_CHANGE'
    observed_directly: bool = False


@dataclass(frozen=True)
class ChronicleArchive:
    entries: tuple[ChronicleEntry, ...] = ()

    @staticmethod
    def _entry_identity(entry: ChronicleEntry) -> tuple[object, ...]:
        return (
            entry.entry_type,
            entry.source_id,
            entry.day,
            entry.tick,
            entry.text,
            entry.settlement_id,
            entry.region_id,
            entry.continent_id,
            entry.layer,
            entry.category,
        )

    def append_entries(self, new_entries: tuple[ChronicleEntry, ...] | list[ChronicleEntry]) -> 'ChronicleArchive':
        seen_entries = {self._entry_identity(entry) for entry in self.entries}
        combined_entries = list(self.entries)
        for entry in new_entries:
            identity = self._entry_identity(entry)
            if identity in seen_entries:
                continue
            combined_entries.append(entry)
            seen_entries.add(identity)
        return ChronicleArchive(entries=tuple(combined_entries))


@dataclass(frozen=True)
class ChronicleView:
    entries_by_time: tuple[ChronicleEntry, ...] = ()
    entries_by_settlement: dict[str, tuple[ChronicleEntry, ...]] = field(default_factory=dict)
    entries_by_region: dict[str, tuple[ChronicleEntry, ...]] = field(default_factory=dict)
    entries_by_continent: dict[str, tuple[ChronicleEntry, ...]] = field(default_factory=dict)

    def get_recent_entries(self, count: int) -> tuple[ChronicleEntry, ...]:
        return self.entries_by_time[:count]

    def get_entries_by_time_range(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> tuple[ChronicleEntry, ...]:
        return tuple(
            entry
            for entry in self.entries_by_time
            if start <= (entry.day, entry.tick) <= end
        )

    def get_settlement_history(self, settlement_id: str) -> tuple[ChronicleEntry, ...]:
        return self.entries_by_settlement.get(settlement_id, ())

    def get_region_history(self, region_id: str) -> tuple[ChronicleEntry, ...]:
        return self.entries_by_region.get(region_id, ())

    def get_continent_history(self, continent_id: str) -> tuple[ChronicleEntry, ...]:
        return self.entries_by_continent.get(continent_id, ())

    def get_player_recent_history(
        self,
        active_settlement_id: str,
        recently_visited_ids: tuple[str, ...] = (),
        limit: int = 10,
    ) -> tuple[ChronicleEntry, ...]:
        relevant_settlement_ids = {active_settlement_id, *recently_visited_ids}
        return tuple(
            entry
            for entry in self.entries_by_time
            if entry.layer in {'region', 'continent'} or entry.settlement_id in relevant_settlement_ids
        )[:limit]


@dataclass(frozen=True)
class ChronicleQueryResult:
    entries: tuple[ChronicleEntry, ...] = ()
    total_count: int = 0
    query_description: str = ''


@dataclass(frozen=True)
class ScopeDiffResult:
    scope_type: str
    scope_id: str
    start: tuple[int, int]
    end: tuple[int, int]
    summary_lines: tuple[str, ...] = ()
    entry_count: int = 0


@dataclass(frozen=True)
class ComparisonItem:
    scope_id: str
    recent_change_count: int
    category_counts: tuple[tuple[str, int], ...] = ()
    summary_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComparisonResult:
    scope_type: str
    items: tuple[ComparisonItem, ...] = ()
    summary_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlayerHistoryEntry:
    entry: ChronicleEntry
    direct: bool
    indirect: bool
    perspective: str


@dataclass(frozen=True)
class InteractionRuntimeState:
    choice_counts: dict[str, int] = field(default_factory=dict)
    last_choice_id: str | None = None
    last_choice_tick: int = 0


@dataclass(frozen=True)
class SpecialNPCState:
    npc_id: str
    status: str = 'DORMANT'
    linked_settlement_id: str | None = None
    signal_count: int = 0
    last_signal_tick: int = 0


@dataclass(frozen=True)
class WorldSummarySnapshot:
    day: int
    tick: int
    settlement_summaries: tuple[str, ...] = ()
    region_summaries: tuple[str, ...] = ()
    continent_summaries: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorldSaveData:
    settlement_states: dict[str, dict]
    region_states: dict[str, dict]
    continent_states: dict[str, dict]
    active_settlement_id: str
    recently_visited_ids: tuple[str, ...] = ()
    pending_influences: tuple[dict, ...] = ()
    propagated_rumor_keys: tuple[str, ...] = ()
    chronicle_archive_entries: tuple[dict, ...] = ()
    interaction_runtime_state: dict = field(default_factory=dict)
    special_npc_states: dict[str, dict] = field(default_factory=dict)


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
    settlement_definitions: dict[str, SettlementDefinition]
    settlement_states: dict[str, WorldState]
    active_settlement_id: str
    recently_visited_ids: tuple[str, ...]
    presentation_state: PresentationState
    simulation_depth: SimulationDepth
    pending_influences: tuple[InfluencePacket, ...] = ()
    settlement_links: tuple[SettlementLink, ...] = ()
    propagated_rumor_keys: tuple[str, ...] = ()
    region_definitions: dict[str, RegionDefinition] = field(default_factory=dict)
    region_states: dict[str, RegionRuntimeState] = field(default_factory=dict)
    continent_definitions: dict[str, ContinentDefinition] = field(default_factory=dict)
    continent_states: dict[str, ContinentRuntimeState] = field(default_factory=dict)
    chronicle_archive: ChronicleArchive = field(default_factory=ChronicleArchive)
    interaction_runtime_state: InteractionRuntimeState = field(default_factory=InteractionRuntimeState)
    special_npc_states: dict[str, SpecialNPCState] = field(default_factory=dict)

    @property
    def settlement_state(self) -> WorldState:
        return self.settlement_states[self.active_settlement_id]

    @property
    def settlement_definition(self) -> SettlementDefinition:
        return self.settlement_definitions[self.active_settlement_id]

    @property
    def region_definition(self) -> RegionDefinition | None:
        settlement = self.settlement_definition
        return self.region_definitions.get(settlement.region_id)


SettlementState = WorldState
