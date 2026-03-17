from __future__ import annotations

from village_rp_engine.config import MEDIATE_TAVERN_CONFLICT_QUEST_ID
from village_rp_engine.core.world_state import WorldState
from village_rp_engine.domain.aftermath_dialogue_templates import AFTERMATH_DIALOGUE_TEMPLATES
from village_rp_engine.domain.dialogue_templates import DIALOGUE_TEMPLATES
from village_rp_engine.domain.event_dialogue_templates import EVENT_DIALOGUE_TEMPLATES
from village_rp_engine.input_aliases import normalize_talk_target
from village_rp_engine.models.dialogue import Dialogue
from village_rp_engine.models.event import TriggeredEvent
from village_rp_engine.models.npc import NPC
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.systems.aftermath_system import AftermathSystem
from village_rp_engine.systems.notice_system import NoticeSystem
from village_rp_engine.systems.player_progress_system import PlayerProgressSystem


ELDER_INDIRECT_DIALOGUES = [
    "농부 쪽에 아직 감정이 남아 있는 모양이군.",
    "저런 불만은 빨리 풀어두는 게 마을을 위한 길일세.",
    "말이 길어지기 전에 누군가 정리해야 할 일도 있지.",
    "작은 다툼도 오래 두면 마을 분위기를 흐리네.",
]


class DialogueSystem:
    def __init__(self, npcs: list[NPC]) -> None:
        self.npcs_by_id = {npc.npc_id: npc for npc in npcs}
        self.npc_id_by_name = {npc.name: npc.npc_id for npc in npcs}
        self.aftermath_system = AftermathSystem()
        self.notice_system = NoticeSystem()
        self.player_progress_system = PlayerProgressSystem()

    def prepare_dialogue_target(self, state: WorldState, action: PlayerAction) -> str | None:
        if action.action_type != "talk" or not action.target_npc_id:
            return None

        target_npc_id = normalize_talk_target(action.target_npc_id)
        target_npc_id = self.npc_id_by_name.get(target_npc_id, target_npc_id)
        npc = self.npcs_by_id.get(target_npc_id)
        if npc is None:
            state.world_log.append("대화 실패: 그런 인물은 없다.")
            return None

        if state.npc_locations.get(target_npc_id) != state.player_location:
            state.world_log.append("대화 실패: 그 인물은 이곳에 없다.")
            return None

        return target_npc_id

    def create_event_dialogues(self, state: WorldState, visible_events: list[TriggeredEvent]) -> list[Dialogue]:
        dialogues: list[Dialogue] = []
        for event in visible_events:
            template_sets = EVENT_DIALOGUE_TEMPLATES.get(event.event_id)
            if not template_sets:
                continue
            selected_lines = self._pick_template(template_sets, state.tick)
            for line in selected_lines:
                speaker_id = line["speaker"]
                npc = self.npcs_by_id[speaker_id]
                recent_state_text = self._select_recent_state_text(speaker_id, state)
                dialogue = Dialogue(
                    speaker_id=speaker_id,
                    speaker_name=npc.name,
                    text=recent_state_text or line["text"],
                    source_type="event",
                )
                dialogues.append(dialogue)
                state.world_log.append(f"현장 대화: {npc.name} -> {dialogue.text}")
        return dialogues

    def resolve_dialogue(
        self,
        state: WorldState,
        target_npc_id: str | None,
        visible_events: list[TriggeredEvent],
    ) -> list[Dialogue]:
        if not target_npc_id:
            return []

        self.player_progress_system.ensure_initialized(state)
        npc = self.npcs_by_id[target_npc_id]
        text = self._select_dialogue_text(target_npc_id, state, visible_events)
        dialogue = Dialogue(
            speaker_id=target_npc_id,
            speaker_name=npc.name,
            text=text,
            source_type="talk",
        )
        state.world_log.append(f"대화: {npc.name} -> {text}")
        return [dialogue]

    def _select_dialogue_text(self, npc_id: str, state: WorldState, visible_events: list[TriggeredEvent]) -> str:
        templates = DIALOGUE_TEMPLATES[npc_id]

        event_templates = self._select_event_templates(templates, visible_events)
        if event_templates is not None:
            return self._pick_template(event_templates, state.tick)

        recent_state_templates = self._select_recent_state_templates(npc_id, state)
        if recent_state_templates is not None:
            return self._pick_template(recent_state_templates, state.tick)

        notice_templates = self._select_notice_templates(npc_id, state)
        if notice_templates is not None:
            return self._pick_template(notice_templates, state.tick)

        quest_templates = self._select_quest_templates(npc_id, state)
        if quest_templates is not None:
            return self._pick_template(quest_templates, state.tick)

        elder_indirect_dialogues = self._select_elder_indirect_dialogues(npc_id, state)
        if elder_indirect_dialogues is not None:
            return self._pick_template(elder_indirect_dialogues, state.tick)

        affinity_templates = self._select_player_affinity_templates(npc_id, state)
        if affinity_templates is not None:
            return self._pick_template(affinity_templates, state.tick)

        if self._should_use_rumor_dialogue(state):
            return self._pick_template(templates["rumor"], state.tick)

        location_templates = templates.get("location", {}).get(state.player_location)
        if location_templates:
            return self._pick_template(location_templates, state.tick)

        time_templates = templates.get("time", {}).get(state.time_phase)
        if time_templates:
            return self._pick_template(time_templates, state.tick)

        return self._pick_template(templates["default"], state.tick)

    def _select_event_templates(
        self,
        templates: dict[str, object],
        visible_events: list[TriggeredEvent],
    ) -> list[str] | None:
        event_map = templates.get("event", {})
        for event in visible_events:
            event_templates = event_map.get(event.event_id)
            if event_templates:
                return event_templates
        return None

    def _select_recent_state_templates(self, npc_id: str, state: WorldState) -> list[str] | None:
        recent_state = self.aftermath_system.get_recent_state(state, npc_id)
        if recent_state is None:
            return None
        return AFTERMATH_DIALOGUE_TEMPLATES.get(npc_id, {}).get(recent_state.state_id)

    def _select_notice_templates(self, npc_id: str, state: WorldState) -> list[str] | None:
        notice = self.notice_system.get_active_notice(state, npc_id)
        if notice is None:
            return None
        notice_map = DIALOGUE_TEMPLATES[npc_id].get("notice", {})
        return notice_map.get(notice.notice_type)

    def _select_quest_templates(self, npc_id: str, state: WorldState) -> list[str] | None:
        if npc_id != "village_elder":
            return None
        quest_map = DIALOGUE_TEMPLATES[npc_id].get("quest", {}).get(MEDIATE_TAVERN_CONFLICT_QUEST_ID, {})
        quest_status = state.quest_status.get(MEDIATE_TAVERN_CONFLICT_QUEST_ID, "not_started")
        if quest_status == "completed":
            return quest_map.get("completed")
        if quest_status == "active":
            return quest_map.get("active")
        if self.player_progress_system._can_offer_mediation_quest(state):
            return quest_map.get("not_started")
        return None

    def _select_elder_indirect_dialogues(self, npc_id: str, state: WorldState) -> list[str] | None:
        if npc_id != "village_elder":
            return None
        has_farmer_complaint = any(
            npc_state.state_id == "complaining_about_blacksmith"
            for npc_state in state.npc_recent_states.get("farmer", [])
        )
        if not has_farmer_complaint:
            return None
        return ELDER_INDIRECT_DIALOGUES

    def _select_player_affinity_templates(self, npc_id: str, state: WorldState) -> list[str] | None:
        if self.player_progress_system.get_player_relationship(state, npc_id) < 1:
            return None
        return DIALOGUE_TEMPLATES[npc_id].get("player_affinity")

    def _select_recent_state_text(self, npc_id: str, state: WorldState) -> str | None:
        recent_state_templates = self._select_recent_state_templates(npc_id, state)
        if recent_state_templates is None:
            return None
        return self._pick_template(recent_state_templates, state.tick)

    def _should_use_rumor_dialogue(self, state: WorldState) -> bool:
        if not state.rumor_log:
            return False

        last_rumor = state.rumor_log[-1]
        rumor_text = last_rumor.text
        return state.player_location in rumor_text or state.time_phase in rumor_text or last_rumor.location == state.player_location

    def _pick_template(self, templates: list, tick: int):
        return templates[(tick - 1) % len(templates)]
