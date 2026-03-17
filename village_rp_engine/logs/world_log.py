from __future__ import annotations

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.relationship import Relationship
from village_rp_engine.models.scene import Scene
from village_rp_engine.systems.relationship_system import RelationshipSystem


RELATIONSHIP_SYSTEM = RelationshipSystem()


def build_tick_header(tick: int, day: int, time_phase: str) -> str:
    return f"[Day {day}][Tick {tick}] 시간대: {time_phase}"


def format_tick_summary(state: WorldState, mode: Mode = Mode.RP) -> str:
    event_lines = [event.outcome_text for event in state.triggered_events] or ["없음"]
    scene_lines = [render_scene(scene, mode) for scene in state.visible_scenes] or ["없음"]
    dialogue_lines = [f'{dialogue.speaker_name}: "{dialogue.text}"' for dialogue in state.dialogues] or ["없음"]
    rumor_lines = [f"Day {rumor.day}: {rumor.text}" for rumor in state.rumor_log[-3:]] or ["없음"]
    relationship_lines = [format_relationship(relationship) for relationship in RELATIONSHIP_SYSTEM.list_relationships(state)] or ["없음"]
    npc_lines = [f"{npc_id}: {location}" for npc_id, location in sorted(state.npc_locations.items())]
    world_lines = "\n".join(f"  - {line}" for line in filter_world_log(state.world_log, mode))

    return "\n".join(
        [
            f"Day {state.day} | Tick {state.tick} | {state.time_phase}",
            f"Player: {state.player_location}",
            "NPC 위치:",
            *[f"  - {line}" for line in npc_lines],
            "발생 이벤트:",
            *[f"  - {line}" for line in event_lines],
            "Visible Scenes:",
            *[f"  - {line}" for line in scene_lines],
            "Dialogues:",
            *[f"  - {line}" for line in dialogue_lines],
            "Relationships:",
            *[f"  - {line}" for line in relationship_lines],
            "Rumor Log:",
            *[f"  - {line}" for line in rumor_lines],
            "World Log:",
            world_lines,
        ]
    )


def render_scene(scene: Scene, mode: Mode) -> str:
    if mode == Mode.OBSERVER:
        return scene.observer_text
    return scene.text


def format_relationship(relationship: Relationship) -> str:
    return f"{relationship.source_npc_id} ↔ {relationship.target_npc_id}: {relationship.score:+d}"


def filter_world_log(world_log: list[str], mode: Mode) -> list[str]:
    if mode == Mode.RP:
        return world_log
    return [
        line
        for line in world_log
        if not line.startswith("플레이어 행동:") and not line.startswith("장면 생성:") and not line.startswith("대화:")
    ]
