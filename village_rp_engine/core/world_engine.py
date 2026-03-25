from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import WorldState
from village_rp_engine.domain.settlement_data import build_phase2_settlements, get_phase2_npc_name_map
from village_rp_engine.logs.chronicle import build_chronicle_entries, build_world_chronicle_entries
from village_rp_engine.logs.world_log import build_tick_header, format_relationship
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.phase1_world import (
    InfluencePacket,
    PresentationDialogue,
    PresentationEventSummary,
    PresentationNPC,
    PresentationState,
    SettlementDefinition,
    SettlementLink,
    SimulationDepth,
    WorldSnapshot,
)
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.models.rumor import Rumor
from village_rp_engine.systems.relationship_system import RelationshipSystem


RELATIONSHIP_SYSTEM = RelationshipSystem()
NPC_NAME_BY_ID = get_phase2_npc_name_map()


def resolve_simulation_depth(
    active_settlement_id: str,
    target_settlement_id: str,
    recently_visited_ids: Iterable[str] | None = None,
) -> SimulationDepth:
    recent_ids = set(recently_visited_ids or [])
    if target_settlement_id == active_settlement_id:
        return SimulationDepth.ACTIVE
    if target_settlement_id in recent_ids:
        return SimulationDepth.RECENT
    return SimulationDepth.UNVISITED


def can_travel_between_settlements(
    active_settlement_id: str,
    target_settlement_id: str,
    links: Iterable[SettlementLink],
) -> bool:
    if active_settlement_id == target_settlement_id:
        return False
    return any(
        link.from_settlement_id == active_settlement_id and link.to_settlement_id == target_settlement_id
        for link in links
    )


def apply_pending_influences(
    settlement_state: WorldState,
    pending_influences: Iterable[InfluencePacket],
) -> tuple[InfluencePacket, ...]:
    remaining_influences: list[InfluencePacket] = []
    economy_profile = dict(settlement_state.economy_profile)
    security = settlement_state.security
    stress = settlement_state.stress
    applied = False

    for influence in pending_influences:
        if influence.target_settlement_id != settlement_state.settlement_id:
            remaining_influences.append(influence)
            continue
        applied = True
        for key, delta in influence.economy_delta.items():
            economy_profile[key] = economy_profile.get(key, 0) + delta
        security += influence.security_delta
        stress += influence.stress_delta

    if applied:
        settlement_state.economy_profile = economy_profile
        settlement_state.security = security
        settlement_state.stress = stress

    return tuple(remaining_influences)


def build_presentation_state(
    settlement_state: WorldState,
    chronicle_entries=None,
) -> PresentationState:
    player_location = settlement_state.player_location
    present_npcs = tuple(
        PresentationNPC(npc_id=npc_id, name=NPC_NAME_BY_ID.get(npc_id, npc_id))
        for npc_id, location in sorted(settlement_state.npc_locations.items())
        if player_location is not None and location == player_location
    )
    npc_status_lines = tuple(
        _build_npc_status_line(settlement_state, npc_id, location)
        for npc_id, location in sorted(settlement_state.npc_locations.items())
    )
    return PresentationState(
        visible_scenes=tuple(scene.text for scene in settlement_state.visible_scenes),
        dialogues=tuple(
            PresentationDialogue(
                speaker_id=dialogue.speaker_id,
                speaker_name=dialogue.speaker_name,
                text=dialogue.text,
            )
            for dialogue in settlement_state.dialogues
        ),
        triggered_event_summaries=tuple(
            PresentationEventSummary(event_id=event.event_id, outcome_text=event.outcome_text)
            for event in settlement_state.triggered_events
        ),
        rumor_lines=tuple(
            f'Day {rumor.day} {rumor.time_phase} | {rumor.text}'
            for rumor in settlement_state.rumor_log[-5:]
        ),
        relationship_lines=tuple(
            format_relationship(relationship)
            for relationship in RELATIONSHIP_SYSTEM.list_relationships(settlement_state)
        ),
        player_relationship_lines=tuple(
            f'{npc_id}: {score:+d}'
            for npc_id, score in sorted(settlement_state.player_relationships.items())
        ),
        quest_lines=tuple(
            f'{quest_id}: {status}'
            for quest_id, status in sorted(settlement_state.quest_status.items())
        ),
        world_log_lines=tuple(settlement_state.world_log),
        chronicle_entries=tuple(chronicle_entries or build_chronicle_entries(settlement_state)),
        present_npcs=present_npcs,
        npc_status_lines=npc_status_lines,
    )


def build_world_snapshot(
    settlement_state: WorldState | None = None,
    simulation_depth: SimulationDepth = SimulationDepth.ACTIVE,
    pending_influences: Iterable[InfluencePacket] = (),
    *,
    settlement_definitions: dict[str, SettlementDefinition] | None = None,
    settlement_states: dict[str, WorldState] | None = None,
    active_settlement_id: str | None = None,
    recently_visited_ids: Iterable[str] = (),
    settlement_links: Iterable[SettlementLink] = (),
    propagated_rumor_keys: Iterable[str] = (),
) -> WorldSnapshot:
    single_settlement_mode = settlement_states is None and settlement_state is not None
    if settlement_states is None:
        if settlement_state is None:
            raise ValueError('settlement_state or settlement_states is required')
        settlement_states = {settlement_state.settlement_id: settlement_state}
        if settlement_definitions is None:
            known_definitions = build_phase2_settlements()
            if settlement_state.settlement_id in known_definitions:
                settlement_definitions = {settlement_state.settlement_id: known_definitions[settlement_state.settlement_id]}
            else:
                settlement_definitions = {}
        active_settlement_id = active_settlement_id or settlement_state.settlement_id
    if settlement_definitions is None:
        settlement_definitions = {}
    if active_settlement_id is None:
        active_settlement_id = next(iter(settlement_states))
    if single_settlement_mode:
        chronicle_entries = build_chronicle_entries(settlement_states[active_settlement_id])
        settlement_links = ()
    else:
        chronicle_entries = build_world_chronicle_entries(settlement_states, active_settlement_id=active_settlement_id)
    return WorldSnapshot(
        settlement_definitions=dict(settlement_definitions),
        settlement_states={settlement_id: clone_settlement_state(state) for settlement_id, state in settlement_states.items()},
        active_settlement_id=active_settlement_id,
        recently_visited_ids=tuple(recently_visited_ids),
        presentation_state=build_presentation_state(settlement_states[active_settlement_id], chronicle_entries=chronicle_entries),
        simulation_depth=simulation_depth,
        pending_influences=tuple(pending_influences),
        settlement_links=tuple(settlement_links),
        propagated_rumor_keys=tuple(propagated_rumor_keys),
    )


class Phase1WorldEngine:
    def __init__(
        self,
        settlement_definitions: dict[str, SettlementDefinition],
        settlement_engines: dict[str, TickEngine],
        settlement_links: Iterable[SettlementLink] = (),
    ) -> None:
        self.settlement_definitions = dict(settlement_definitions)
        self.settlement_engines = dict(settlement_engines)
        self.settlement_links = tuple(settlement_links)

    @property
    def settlement_engine(self) -> TickEngine:
        return self.settlement_engines[next(iter(self.settlement_engines))]

    def get_settlement_engine(self, settlement_id: str) -> TickEngine:
        return self.settlement_engines[settlement_id]

    def run_step(
        self,
        snapshot: WorldSnapshot,
        mode: Mode,
        action: PlayerAction | None = None,
        target_settlement_id: str | None = None,
        recently_visited_ids: Iterable[str] | None = None,
    ) -> WorldSnapshot:
        action = action or PlayerAction.wait()
        states = {
            settlement_id: clone_settlement_state(state)
            for settlement_id, state in snapshot.settlement_states.items()
        }
        active_links = snapshot.settlement_links or self.settlement_links
        active_state = states[snapshot.active_settlement_id]
        travel_target = target_settlement_id
        if action.action_type == 'travel' and action.target_settlement_id:
            travel_target = action.target_settlement_id
        if action.action_type == 'travel' and not can_travel_between_settlements(
            snapshot.active_settlement_id,
            travel_target or snapshot.active_settlement_id,
            active_links,
        ):
            active_state.world_log.append(f'이동 실패: {snapshot.active_settlement_id} -> {travel_target}')
            action = PlayerAction.wait()
            travel_target = snapshot.active_settlement_id
        next_active_settlement_id = travel_target or snapshot.active_settlement_id
        next_recently_visited_ids = tuple(
            _build_recently_visited_ids(
                snapshot.active_settlement_id,
                next_active_settlement_id,
                snapshot.recently_visited_ids,
            )
        )

        if action.action_type == 'travel' and next_active_settlement_id in states:
            origin_state = states[snapshot.active_settlement_id]
            origin_state.previous_player_location = origin_state.player_location
            origin_state.player_location = None
            destination_state = states[next_active_settlement_id]
            public_locations = [location for location in self.settlement_definitions[next_active_settlement_id].locations if location != '집']
            if public_locations:
                destination_state.player_location = public_locations[0]
                destination_state.previous_player_location = destination_state.player_location

        if action.action_type == 'talk':
            active_state = states[snapshot.active_settlement_id]
            active_state = self._run_active_step(self.get_settlement_engine(snapshot.active_settlement_id), active_state, mode, action)
            states[snapshot.active_settlement_id] = active_state
            chronicle_entries = build_world_chronicle_entries(states, active_settlement_id=snapshot.active_settlement_id)
            return WorldSnapshot(
                settlement_definitions=dict(self.settlement_definitions),
                settlement_states=states,
                active_settlement_id=snapshot.active_settlement_id,
                recently_visited_ids=tuple(snapshot.recently_visited_ids),
                presentation_state=build_presentation_state(active_state, chronicle_entries=chronicle_entries),
                simulation_depth=SimulationDepth.ACTIVE,
                pending_influences=tuple(snapshot.pending_influences),
                settlement_links=active_links,
                propagated_rumor_keys=tuple(snapshot.propagated_rumor_keys),
            )

        remaining_influences = tuple(snapshot.pending_influences)
        depth_map: dict[str, SimulationDepth] = {}
        for settlement_id, state in states.items():
            depth = resolve_simulation_depth(
                active_settlement_id=next_active_settlement_id,
                target_settlement_id=settlement_id,
                recently_visited_ids=recently_visited_ids or next_recently_visited_ids,
            )
            depth_map[settlement_id] = depth
            if depth != SimulationDepth.ACTIVE:
                state.player_location = None
            remaining_influences = apply_pending_influences(state, remaining_influences)
            if depth == SimulationDepth.ACTIVE:
                local_action = action if settlement_id == next_active_settlement_id and action.action_type != 'travel' else PlayerAction.wait()
                states[settlement_id] = self._run_active_step(self.get_settlement_engine(settlement_id), state, mode, local_action)
            elif depth == SimulationDepth.RECENT:
                states[settlement_id] = self._run_recent_step(self.get_settlement_engine(settlement_id), state)
            else:
                states[settlement_id] = self._run_unvisited_step(self.get_settlement_engine(settlement_id), state)

        propagated_rumor_keys, states = self._propagate_rumors(
            states,
            snapshot.propagated_rumor_keys,
            active_links,
        )
        active_state = states[next_active_settlement_id]
        chronicle_entries = build_world_chronicle_entries(states, active_settlement_id=next_active_settlement_id)
        return WorldSnapshot(
            settlement_definitions=dict(self.settlement_definitions),
            settlement_states=states,
            active_settlement_id=next_active_settlement_id,
            recently_visited_ids=next_recently_visited_ids,
            presentation_state=build_presentation_state(active_state, chronicle_entries=chronicle_entries),
            simulation_depth=depth_map[next_active_settlement_id],
            pending_influences=remaining_influences,
            settlement_links=active_links,
            propagated_rumor_keys=tuple(sorted(propagated_rumor_keys)),
        )

    def _run_active_step(self, settlement_engine: TickEngine, settlement_state: WorldState, mode: Mode, action: PlayerAction | None) -> WorldState:
        from village_rp_engine.core.mode_controller import run_mode_tick

        if mode == Mode.OBSERVER:
            return run_mode_tick(settlement_engine, settlement_state, mode)

        next_action = action or PlayerAction.wait()
        return run_mode_tick(
            settlement_engine,
            settlement_state,
            mode,
            action_provider=lambda next_action=next_action: next_action,
        )

    def _run_recent_step(self, settlement_engine: TickEngine, settlement_state: WorldState) -> WorldState:
        next_state = _advance_state_shell(settlement_engine, settlement_state, label='recent')
        triggered_events = settlement_engine.event_system.trigger_events(next_state)
        next_state.triggered_events = triggered_events
        settlement_engine.relationship_system.apply_event_effects(next_state, triggered_events)
        settlement_engine.aftermath_system.apply_event_effects(next_state, triggered_events)
        next_state.rumor_log = [
            *settlement_state.rumor_log,
            *settlement_engine.rumor_system.create_rumors(next_state, triggered_events),
        ]
        if not triggered_events:
            next_state.world_log.append('recent settlement update: 사건 없음')
        next_state.visible_scenes = []
        next_state.dialogues = []
        next_state.player_location = None
        return next_state

    def _run_unvisited_step(self, settlement_engine: TickEngine, settlement_state: WorldState) -> WorldState:
        next_state = _advance_state_shell(settlement_engine, settlement_state, label='unvisited')
        next_state.triggered_events = []
        next_state.visible_scenes = []
        next_state.dialogues = []
        next_state.world_log.append('unvisited settlement update: numeric only')
        next_state.player_location = None
        return next_state

    def _propagate_rumors(
        self,
        states: dict[str, WorldState],
        propagated_rumor_keys: Iterable[str],
        settlement_links: Iterable[SettlementLink],
    ) -> tuple[set[str], dict[str, WorldState]]:
        seen_keys = set(propagated_rumor_keys)
        for link in settlement_links:
            if link.from_settlement_id not in states or link.to_settlement_id not in states:
                continue
            source_state = states[link.from_settlement_id]
            target_state = states[link.to_settlement_id]
            for rumor in source_state.rumor_log[-3:]:
                origin_settlement_id = rumor.origin_settlement_id or link.from_settlement_id
                rumor_age = max(0, source_state.tick - rumor.tick)
                freshness = rumor.freshness - 1
                if rumor_age < link.rumor_speed or freshness <= 0:
                    continue
                propagation_key = f'{origin_settlement_id}:{rumor.source_event_id}:{rumor.tick}:{link.to_settlement_id}'
                if propagation_key in seen_keys:
                    continue
                seen_keys.add(propagation_key)
                target_state.rumor_log.append(
                    Rumor(
                        source_event_id=rumor.source_event_id,
                        tick=target_state.tick,
                        day=target_state.day,
                        time_phase=target_state.time_phase,
                        location=_default_context_location(target_state),
                        text=f'{origin_settlement_id}에서 {rumor.text}',
                        origin_settlement_id=origin_settlement_id,
                        freshness=freshness,
                        intensity=max(1, rumor.intensity - 1),
                        is_remote=True,
                    )
                )
                target_state.world_log.append(f'외부 소문 유입: {origin_settlement_id} -> {link.to_settlement_id}')
        return seen_keys, states


def clone_settlement_state(state: WorldState) -> WorldState:
    return replace(
        state,
        economy_profile=dict(state.economy_profile),
        npc_locations=dict(state.npc_locations),
        previous_npc_locations=dict(state.previous_npc_locations),
        triggered_events=list(state.triggered_events),
        visible_scenes=list(state.visible_scenes),
        dialogues=list(state.dialogues),
        rumor_log=list(state.rumor_log),
        world_log=list(state.world_log),
        relationships=dict(state.relationships),
        player_relationships=dict(state.player_relationships),
        quest_status=dict(state.quest_status),
        quest_contacts={quest_id: set(contacts) for quest_id, contacts in state.quest_contacts.items()},
        npc_recent_states={npc_id: list(states) for npc_id, states in state.npc_recent_states.items()},
        player_notices=list(state.player_notices),
        locked_npc_ids_for_tick=set(state.locked_npc_ids_for_tick),
        event_last_trigger_tick=dict(state.event_last_trigger_tick),
        rumor_history_keys=set(state.rumor_history_keys),
        recent_scene_event_ids=set(state.recent_scene_event_ids),
    )


def _advance_state_shell(settlement_engine: TickEngine, state: WorldState, label: str) -> WorldState:
    next_phase = settlement_engine.time_system.next_phase(state.time_phase)
    next_tick = state.tick + 1
    next_day = state.day + 1 if state.time_phase == '새벽' and next_phase == '아침' else state.day
    next_state = replace(
        state,
        tick=next_tick,
        day=next_day,
        time_phase=next_phase,
        previous_player_location=state.player_location,
        previous_npc_locations=dict(state.npc_locations),
        triggered_events=[],
        visible_scenes=[],
        dialogues=[],
        world_log=[build_tick_header(next_tick, next_day, next_phase), f'{label} settlement update'],
        relationships=dict(state.relationships),
        player_relationships=dict(state.player_relationships),
        quest_status=dict(state.quest_status),
        quest_contacts={quest_id: set(contacts) for quest_id, contacts in state.quest_contacts.items()},
        npc_recent_states={npc_id: list(states) for npc_id, states in state.npc_recent_states.items()},
        player_notices=list(state.player_notices),
        locked_npc_ids_for_tick=set(),
        event_last_trigger_tick=dict(state.event_last_trigger_tick),
        rumor_history_keys=set(state.rumor_history_keys),
        recent_scene_event_ids=set(),
        rumor_log=list(state.rumor_log),
    )
    settlement_engine.relationship_system.ensure_initial_relationships(next_state)
    settlement_engine.aftermath_system.expire_states(next_state, next_day)
    settlement_engine.notice_system.expire_notices(next_state, next_tick)
    next_state.npc_locations = settlement_engine.movement_system.resolve_locations_for_phase(next_phase)
    return next_state


def _build_recently_visited_ids(
    previous_active_settlement_id: str,
    next_active_settlement_id: str,
    existing_recently_visited_ids: Iterable[str],
) -> list[str]:
    recent_ids: list[str] = []
    for settlement_id in [previous_active_settlement_id, *existing_recently_visited_ids]:
        if settlement_id == next_active_settlement_id or settlement_id in recent_ids:
            continue
        recent_ids.append(settlement_id)
    return recent_ids[:2]


def _default_context_location(settlement_state: WorldState) -> str:
    for location in settlement_state.npc_locations.values():
        if location != '집':
            return location
    return '광장'


def _build_npc_status_line(settlement_state: WorldState, npc_id: str, location: str) -> str:
    state_ids = [recent_state.state_id for recent_state in settlement_state.npc_recent_states.get(npc_id, [])]
    status_text = ', '.join(state_ids) if state_ids else '없음'
    return f"{NPC_NAME_BY_ID.get(npc_id, npc_id)} ({npc_id}) @ {location} | recent_state: {status_text}"
