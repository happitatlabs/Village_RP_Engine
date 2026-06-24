from __future__ import annotations

from village_rp_engine.config import MEDIATE_TAVERN_CONFLICT_QUEST_ID, PLAYER_RELATIONSHIP_NPC_IDS
from village_rp_engine.core.world_state import WorldState, build_initial_player_relationships
from village_rp_engine.systems.aftermath_system import AftermathSystem
from village_rp_engine.systems.relationship_system import RelationshipSystem


TRUSTED_GUEST_RECOGNITION_SCORE = 2


class PlayerProgressSystem:
    def __init__(self, min_score: int = -2, max_score: int = 2) -> None:
        self.min_score = min_score
        self.max_score = max_score
        self.aftermath_system = AftermathSystem()
        self.relationship_system = RelationshipSystem()

    def ensure_initialized(self, state: WorldState) -> None:
        if not state.player_relationships:
            state.player_relationships = build_initial_player_relationships()
        for npc_id in PLAYER_RELATIONSHIP_NPC_IDS:
            state.player_relationships.setdefault(npc_id, 0)
        state.resident_status.setdefault(state.settlement_id, "outsider")
        state.recognition_score.setdefault(state.settlement_id, 0)
        state.recognition_blocked_until_tick.setdefault(state.settlement_id, 0)
        state.quest_status.setdefault(MEDIATE_TAVERN_CONFLICT_QUEST_ID, "not_started")
        state.quest_contacts.setdefault(MEDIATE_TAVERN_CONFLICT_QUEST_ID, set())
        state.quest_refusal_penalty_ticks.setdefault(MEDIATE_TAVERN_CONFLICT_QUEST_ID, 0)

    def handle_player_talk(self, state: WorldState, target_npc_id: str | None) -> None:
        self.ensure_initialized(state)
        if target_npc_id is None:
            self._refresh_mediation_quest(state)
            return

        if target_npc_id == "village_elder" and self.can_offer_mediation_quest(state):
            if self._get_quest_status(state) == "not_started":
                self._set_mediation_quest_pending(state)
        elif self._get_quest_status(state) == "active" and target_npc_id in {"farmer", "blacksmith"}:
            state.quest_contacts[MEDIATE_TAVERN_CONFLICT_QUEST_ID].add(target_npc_id)
            state.world_log.append(f"퀘스트 진행: {target_npc_id}와 이야기해 보았다.")

        self._refresh_mediation_quest(state)

    def refresh_after_tick(self, state: WorldState) -> None:
        self.ensure_initialized(state)
        self._tick_down_refusal_penalty(state)
        self._refresh_mediation_quest(state)

    def get_player_relationship(self, state: WorldState, npc_id: str) -> int:
        self.ensure_initialized(state)
        return state.player_relationships.get(npc_id, 0)

    def can_offer_mediation_quest(self, state: WorldState) -> bool:
        status = self._get_quest_status(state)
        if status not in {"not_started", "pending", "refused"}:
            return False
        if status == "refused" and state.quest_refusal_penalty_ticks.get(MEDIATE_TAVERN_CONFLICT_QUEST_ID, 0) > 0:
            return False
        if self.relationship_system.get_relationship_score(state, "blacksmith", "farmer") < 0:
            return True
        farmer_state = self.aftermath_system.get_recent_state(state, "farmer")
        blacksmith_state = self.aftermath_system.get_recent_state(state, "blacksmith")
        return (
            farmer_state is not None
            and farmer_state.state_id == "complaining_about_blacksmith"
            and blacksmith_state is not None
            and blacksmith_state.state_id == "irritated_with_farmer"
        )

    def accept_mediation_quest(self, state: WorldState) -> None:
        self.ensure_initialized(state)
        if not self.can_offer_mediation_quest(state):
            return
        state.quest_status[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = "active"
        state.quest_contacts[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = set()
        state.quest_refusal_penalty_ticks[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = 0
        state.recognition_blocked_until_tick[state.settlement_id] = 0
        state.resident_status[state.settlement_id] = "trusted_guest"
        self._apply_player_relationship_delta(state, "village_elder", 1)
        state.world_log.append(f"퀘스트 시작: {MEDIATE_TAVERN_CONFLICT_QUEST_ID}")
        state.world_log.append("상태 부여: 촌장의 부탁을 받아 마을 사람들의 말다툼에 개입하기로 했다.")

    def defer_mediation_quest(self, state: WorldState) -> None:
        self.ensure_initialized(state)
        if not self.can_offer_mediation_quest(state):
            return
        self._set_mediation_quest_pending(state)
        state.world_log.append("상태 부여: 촌장의 부탁은 아직 답을 기다리고 있다.")

    def refuse_mediation_quest(self, state: WorldState, penalty_ticks: int = 10) -> None:
        self.ensure_initialized(state)
        if not self.can_offer_mediation_quest(state):
            return
        state.quest_status[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = "refused"
        state.quest_contacts[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = set()
        state.quest_refusal_penalty_ticks[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = penalty_ticks
        state.resident_status[state.settlement_id] = "outsider"
        state.recognition_score[state.settlement_id] = 0
        state.recognition_blocked_until_tick[state.settlement_id] = state.tick + penalty_ticks
        state.world_log.append("상태 부여: 촌장은 아직 당신을 마을 사람으로 받아들이기엔 이르다고 판단한 듯하다.")

    def _set_mediation_quest_pending(self, state: WorldState) -> None:
        state.quest_status[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = "pending"
        state.quest_contacts[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = set()
        state.quest_refusal_penalty_ticks[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = 0
        state.recognition_blocked_until_tick[state.settlement_id] = 0

    def _tick_down_refusal_penalty(self, state: WorldState) -> None:
        remaining = state.quest_refusal_penalty_ticks.get(MEDIATE_TAVERN_CONFLICT_QUEST_ID, 0)
        if remaining <= 0:
            return
        state.quest_refusal_penalty_ticks[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = remaining - 1
        if remaining == 1 and self._get_quest_status(state) == "refused":
            state.recognition_blocked_until_tick[state.settlement_id] = state.tick
            self.record_recognition_event(state)

    def _refresh_mediation_quest(self, state: WorldState) -> None:
        if self._get_quest_status(state) != "active":
            return
        contacts = state.quest_contacts[MEDIATE_TAVERN_CONFLICT_QUEST_ID]
        if not {"farmer", "blacksmith"}.issubset(contacts):
            return
        if self._has_active_conflict_state(state, "farmer", "complaining_about_blacksmith"):
            return
        if self._has_active_conflict_state(state, "blacksmith", "irritated_with_farmer"):
            return

        state.quest_status[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = "completed"
        state.quest_refusal_penalty_ticks[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = 0
        state.recognition_blocked_until_tick[state.settlement_id] = 0
        state.resident_status[state.settlement_id] = "resident"
        self._apply_player_relationship_delta(state, "village_elder", 1)
        self._apply_player_relationship_delta(state, "farmer", 1)
        self._apply_player_relationship_delta(state, "blacksmith", 1)
        state.world_log.append(f"퀘스트 완료: {MEDIATE_TAVERN_CONFLICT_QUEST_ID}")
        state.world_log.append("상태 부여: 플레이어는 농부와 대장장이 사이를 중재하려 했다.")
        state.world_log.append("상태 부여: 두 사람은 아직 어색하지만, 적어도 서로를 피하지는 않게 되었다.")
        state.world_log.append("상태 부여: 촌장은 플레이어를 회색언덕의 주민으로 인정했다.")

    def record_recognition_event(self, state: WorldState, amount: int = 1) -> None:
        self.ensure_initialized(state)
        if state.resident_status.get(state.settlement_id) == "resident":
            return
        next_score = state.recognition_score.get(state.settlement_id, 0) + amount
        state.recognition_score[state.settlement_id] = next_score
        if next_score >= TRUSTED_GUEST_RECOGNITION_SCORE:
            state.resident_status[state.settlement_id] = "trusted_guest"
        elif next_score >= 1:
            state.resident_status[state.settlement_id] = "guest"
        state.world_log.append("상태 부여: 작은 일들을 도우며 마을 사람들의 시선이 조금 누그러졌다.")

    def _has_active_conflict_state(self, state: WorldState, npc_id: str, state_id: str) -> bool:
        recent_state = self.aftermath_system.get_recent_state(state, npc_id)
        return recent_state is not None and recent_state.state_id == state_id

    def _get_quest_status(self, state: WorldState) -> str:
        return state.quest_status[MEDIATE_TAVERN_CONFLICT_QUEST_ID]

    def _apply_player_relationship_delta(self, state: WorldState, npc_id: str, delta: int) -> None:
        next_score = self._clamp(self.get_player_relationship(state, npc_id) + delta)
        state.player_relationships[npc_id] = next_score
        state.world_log.append(f"플레이어 호감도 변화: {npc_id} -> {next_score:+d}")

    def _clamp(self, score: int) -> int:
        return max(self.min_score, min(self.max_score, score))
