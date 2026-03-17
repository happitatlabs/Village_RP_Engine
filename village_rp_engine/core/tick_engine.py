from __future__ import annotations

import random
from dataclasses import replace

from village_rp_engine.core.time_system import TimeSystem
from village_rp_engine.core.world_state import WorldState
from village_rp_engine.logs.world_log import build_tick_header
from village_rp_engine.models.event import EventDefinition
from village_rp_engine.models.npc import NPC
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.systems.aftermath_system import AftermathSystem
from village_rp_engine.systems.dialogue_system import DialogueSystem
from village_rp_engine.systems.event_system import EventSystem
from village_rp_engine.systems.movement_system import MovementSystem
from village_rp_engine.systems.narration_system import NarrationSystem
from village_rp_engine.systems.notice_system import NoticeSystem
from village_rp_engine.systems.perception_system import PerceptionSystem
from village_rp_engine.systems.player_action_system import PlayerActionSystem
from village_rp_engine.systems.relationship_system import RelationshipSystem
from village_rp_engine.systems.rumor_system import RumorSystem


class TickEngine:
    def __init__(
        self,
        npcs: list[NPC],
        schedules: dict[str, dict[str, str]],
        event_definitions: list[EventDefinition],
        seed: int = 0,
    ) -> None:
        self.time_system = TimeSystem()
        self.movement_system = MovementSystem(npcs=npcs, schedules=schedules)
        self.event_system = EventSystem(event_definitions=event_definitions, rng=random.Random(seed))
        self.perception_system = PerceptionSystem()
        self.narration_system = NarrationSystem(npcs=npcs)
        self.player_action_system = PlayerActionSystem()
        self.aftermath_system = AftermathSystem()
        self.notice_system = NoticeSystem()
        self.dialogue_system = DialogueSystem(npcs=npcs)
        self.relationship_system = RelationshipSystem()
        self.rumor_system = RumorSystem(npcs=npcs)

    def run_tick(self, state: WorldState, player_action: PlayerAction | None = None) -> WorldState:
        next_phase = self.time_system.next_phase(state.time_phase)
        next_tick = state.tick + 1
        next_day = state.day + 1 if state.time_phase == "새벽" and next_phase == "아침" else state.day
        world_log = [build_tick_header(next_tick, next_day, next_phase)]

        working_state = replace(
            state,
            tick=next_tick,
            day=next_day,
            time_phase=next_phase,
            previous_player_location=state.player_location,
            previous_npc_locations=dict(state.npc_locations),
            triggered_events=[],
            visible_scenes=[],
            dialogues=[],
            world_log=world_log,
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
        )
        self.relationship_system.ensure_initial_relationships(working_state)
        self.aftermath_system.expire_states(working_state, next_day)
        self.notice_system.expire_notices(working_state, next_tick)

        if not working_state.npc_locations:
            working_state.npc_locations = self.movement_system.resolve_locations_for_phase(state.time_phase)

        action = player_action or PlayerAction.wait()
        self.player_action_system.apply_action(working_state, action)
        pending_talk_npc_id = self.dialogue_system.prepare_dialogue_target(working_state, action)
        if pending_talk_npc_id is not None:
            pending_npc = self.dialogue_system.npcs_by_id[pending_talk_npc_id]
            working_state.locked_npc_ids_for_tick.add(pending_talk_npc_id)
            working_state.world_log.append(f"대화 중: {pending_npc.name} 이동 보류")
        working_state.npc_locations = self.movement_system.move_npcs(working_state)
        self.notice_system.create_player_notices(working_state)
        triggered_events = self.event_system.trigger_events(working_state)
        working_state.triggered_events = triggered_events
        self.relationship_system.apply_event_effects(working_state, triggered_events)
        self.aftermath_system.apply_event_effects(working_state, triggered_events)

        visible_events, hidden_events = self.perception_system.split_events_by_visibility(working_state, triggered_events)
        working_state.visible_scenes = self.narration_system.create_scenes(
            working_state,
            visible_events,
            suppress_arrival_and_idle=pending_talk_npc_id is not None,
        )
        event_dialogues = self.dialogue_system.create_event_dialogues(working_state, visible_events)
        talk_dialogues = self.dialogue_system.resolve_dialogue(working_state, pending_talk_npc_id, visible_events)
        working_state.dialogues = [*event_dialogues, *talk_dialogues]

        new_rumors = self.rumor_system.create_rumors(working_state, hidden_events)
        working_state.rumor_log = [*state.rumor_log, *new_rumors]
        if any(rumor.source_event_id == "argument_at_tavern" for rumor in new_rumors):
            self.aftermath_system.assign_state(
                working_state,
                npc_id="guard_captain",
                state_id="watchful_after_tavern_argument",
                source_event_id="argument_at_tavern",
                expires_day=working_state.day + 1,
            )

        if not triggered_events:
            working_state.world_log.append("사건 없음")

        return working_state
