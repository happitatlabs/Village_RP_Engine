from __future__ import annotations

from village_rp_engine.config import MEDIATE_TAVERN_CONFLICT_QUEST_ID, PLAYER_RELATIONSHIP_NPC_IDS
from village_rp_engine.core.world_state import WorldState, build_initial_player_relationships
from village_rp_engine.systems.aftermath_system import AftermathSystem
from village_rp_engine.systems.relationship_system import RelationshipSystem


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
        state.quest_status.setdefault(MEDIATE_TAVERN_CONFLICT_QUEST_ID, "not_started")
        state.quest_contacts.setdefault(MEDIATE_TAVERN_CONFLICT_QUEST_ID, set())

    def handle_player_talk(self, state: WorldState, target_npc_id: str | None) -> None:
        self.ensure_initialized(state)
        if target_npc_id is None:
            self._refresh_mediation_quest(state)
            return

        if target_npc_id == "village_elder" and self._can_offer_mediation_quest(state):
            self._activate_mediation_quest(state)
        elif self._get_quest_status(state) == "active" and target_npc_id in {"farmer", "blacksmith"}:
            state.quest_contacts[MEDIATE_TAVERN_CONFLICT_QUEST_ID].add(target_npc_id)
            state.world_log.append(f"퀘스트 진행: {target_npc_id}와 이야기해 보았다.")

        self._refresh_mediation_quest(state)

    def refresh_after_tick(self, state: WorldState) -> None:
        self.ensure_initialized(state)
        self._refresh_mediation_quest(state)

    def get_player_relationship(self, state: WorldState, npc_id: str) -> int:
        self.ensure_initialized(state)
        return state.player_relationships.get(npc_id, 0)

    def _can_offer_mediation_quest(self, state: WorldState) -> bool:
        if self._get_quest_status(state) != "not_started":
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

    def _activate_mediation_quest(self, state: WorldState) -> None:
        state.quest_status[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = "active"
        state.quest_contacts[MEDIATE_TAVERN_CONFLICT_QUEST_ID] = set()
        self._apply_player_relationship_delta(state, "village_elder", 1)
        state.world_log.append(f"퀘스트 시작: {MEDIATE_TAVERN_CONFLICT_QUEST_ID}")

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
        self._apply_player_relationship_delta(state, "village_elder", 1)
        self._apply_player_relationship_delta(state, "farmer", 1)
        self._apply_player_relationship_delta(state, "blacksmith", 1)
        state.world_log.append(f"퀘스트 완료: {MEDIATE_TAVERN_CONFLICT_QUEST_ID}")

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
