from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import WorldState
from village_rp_engine.domain.settlement_data import get_phase1_npc_name_map
from village_rp_engine.logs.chronicle import build_chronicle_entries
from village_rp_engine.logs.world_log import format_relationship
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.phase1_world import (
    InfluencePacket,
    PresentationDialogue,
    PresentationEventSummary,
    PresentationNPC,
    PresentationState,
    SimulationDepth,
    WorldSnapshot,
)
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.systems.relationship_system import RelationshipSystem


RELATIONSHIP_SYSTEM = RelationshipSystem()
NPC_NAME_BY_ID = get_phase1_npc_name_map()


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


def build_presentation_state(settlement_state: WorldState) -> PresentationState:
    present_npcs = tuple(
        PresentationNPC(npc_id=npc_id, name=NPC_NAME_BY_ID.get(npc_id, npc_id))
        for npc_id, location in sorted(settlement_state.npc_locations.items())
        if location == settlement_state.player_location
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
        chronicle_entries=tuple(build_chronicle_entries(settlement_state)),
        present_npcs=present_npcs,
        npc_status_lines=npc_status_lines,
    )


def build_world_snapshot(
    settlement_state: WorldState,
    simulation_depth: SimulationDepth = SimulationDepth.ACTIVE,
    pending_influences: Iterable[InfluencePacket] = (),
) -> WorldSnapshot:
    return WorldSnapshot(
        settlement_state=settlement_state,
        presentation_state=build_presentation_state(settlement_state),
        simulation_depth=simulation_depth,
        pending_influences=tuple(pending_influences),
    )


class Phase1WorldEngine:
    def __init__(self, settlement_engine: TickEngine) -> None:
        self.settlement_engine = settlement_engine

    def run_step(
        self,
        snapshot: WorldSnapshot,
        mode: Mode,
        action: PlayerAction | None = None,
        target_settlement_id: str | None = None,
        recently_visited_ids: Iterable[str] | None = None,
    ) -> WorldSnapshot:
        settlement_state = clone_settlement_state(snapshot.settlement_state)
        active_settlement_id = settlement_state.settlement_id
        resolved_target_settlement_id = target_settlement_id or settlement_state.settlement_id
        simulation_depth = resolve_simulation_depth(
            active_settlement_id=active_settlement_id,
            target_settlement_id=resolved_target_settlement_id,
            recently_visited_ids=recently_visited_ids,
        )
        remaining_influences = apply_pending_influences(settlement_state, snapshot.pending_influences)

        if simulation_depth == SimulationDepth.ACTIVE:
            settlement_state = self._run_active_step(settlement_state, mode, action)
        elif simulation_depth == SimulationDepth.RECENT:
            settlement_state = settlement_state
        else:
            settlement_state = settlement_state

        return WorldSnapshot(
            settlement_state=settlement_state,
            presentation_state=build_presentation_state(settlement_state),
            simulation_depth=simulation_depth,
            pending_influences=remaining_influences,
        )

    def _run_active_step(self, settlement_state: WorldState, mode: Mode, action: PlayerAction | None) -> WorldState:
        from village_rp_engine.core.mode_controller import run_mode_tick

        if mode == Mode.OBSERVER:
            return run_mode_tick(self.settlement_engine, settlement_state, mode)

        next_action = action or PlayerAction.wait()
        return run_mode_tick(
            self.settlement_engine,
            settlement_state,
            mode,
            action_provider=lambda next_action=next_action: next_action,
        )


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


def _build_npc_status_line(settlement_state: WorldState, npc_id: str, location: str) -> str:
    state_ids = [recent_state.state_id for recent_state in settlement_state.npc_recent_states.get(npc_id, [])]
    status_text = ', '.join(state_ids) if state_ids else '없음'
    return f"{NPC_NAME_BY_ID.get(npc_id, npc_id)} ({npc_id}) @ {location} | recent_state: {status_text}"
