from __future__ import annotations

import random

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.event import EventDefinition, TriggeredEvent


class EventSystem:
    def __init__(self, event_definitions: list[EventDefinition], rng: random.Random | None = None) -> None:
        self.event_definitions = event_definitions
        self.rng = rng or random.Random()

    def trigger_events(self, state: WorldState) -> list[TriggeredEvent]:
        triggered: list[TriggeredEvent] = []
        replaced_event_ids: set[str] = set()

        follow_up_event = self._trigger_farmer_grumbling_square(state)
        if follow_up_event is not None:
            triggered.append(follow_up_event)
            replaced_event_ids.add("morning_chat_square")

        for definition in self.event_definitions:
            if definition.event_id in replaced_event_ids:
                continue
            if definition.time_phase != state.time_phase:
                continue
            if not self._actors_match(definition, state.npc_locations):
                continue
            if self._is_on_cooldown(definition, state):
                continue
            if self.rng.random() > definition.probability:
                continue

            event = TriggeredEvent(
                event_id=definition.event_id,
                time_phase=definition.time_phase,
                location=definition.location,
                actor_ids=definition.required_actor_ids,
                outcome_text=definition.outcome_text,
                rumor_text=definition.rumor_text,
                narration_text=definition.narration_text,
                observer_narration_text=definition.observer_narration_text,
                rumor_base_score=definition.rumor_base_score,
                witnessed=False,
            )
            triggered.append(event)
            state.event_last_trigger_tick[event.event_id] = state.tick
            state.world_log.append(f"이벤트 발생: {event.outcome_text}")
        return triggered

    def _trigger_farmer_grumbling_square(self, state: WorldState) -> TriggeredEvent | None:
        active_state_ids = {npc_state.state_id for npc_state in state.npc_recent_states.get("farmer", [])}
        if state.time_phase != "아침":
            return None
        if state.npc_locations.get("farmer") != "광장":
            return None
        if "complaining_about_blacksmith" not in active_state_ids:
            return None
        if self._is_follow_up_on_cooldown("farmer_grumbling_square", state, cooldown_tick=0):
            return None

        event = TriggeredEvent(
            event_id="farmer_grumbling_square",
            time_phase="아침",
            location="광장",
            actor_ids=("farmer",),
            outcome_text="농부가 광장에서 어젯밤 말다툼을 곱씹으며 불평을 늘어놓았다.",
            rumor_text="광장에서 농부가 어젯밤 소란을 두고 불평했다는 말이 돌았다.",
            narration_text="광장에서는 농부가 어젯밤 소란을 떠올리며 못내 못마땅한 표정으로 투덜거리고 있었다.",
            observer_narration_text="광장에서 농부가 어젯밤 소란을 떠올리며 불만 섞인 말을 이어가고 있었다.",
            rumor_base_score=0,
            witnessed=False,
        )
        state.event_last_trigger_tick[event.event_id] = state.tick
        state.world_log.append(f"이벤트 발생: {event.outcome_text}")
        return event

    def _actors_match(self, definition: EventDefinition, npc_locations: dict[str, str]) -> bool:
        return all(npc_locations.get(actor_id) == definition.location for actor_id in definition.required_actor_ids)

    def _is_on_cooldown(self, definition: EventDefinition, state: WorldState) -> bool:
        last_trigger_tick = state.event_last_trigger_tick.get(definition.event_id)
        if last_trigger_tick is None:
            return False
        return state.tick - last_trigger_tick <= definition.cooldown_tick

    def _is_follow_up_on_cooldown(self, event_id: str, state: WorldState, cooldown_tick: int) -> bool:
        last_trigger_tick = state.event_last_trigger_tick.get(event_id)
        if last_trigger_tick is None:
            return False
        return state.tick - last_trigger_tick <= cooldown_tick
