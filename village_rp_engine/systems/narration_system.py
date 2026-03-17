from __future__ import annotations

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.domain.scene_templates import render_arrival_scene, render_event_scene, render_idle_scene, render_notice_scene
from village_rp_engine.models.event import TriggeredEvent
from village_rp_engine.models.npc import NPC
from village_rp_engine.models.scene import Scene


class NarrationSystem:
    def __init__(self, npcs: list[NPC]) -> None:
        self.npc_names = {npc.npc_id: npc.name for npc in npcs}

    def create_scenes(
        self,
        state: WorldState,
        visible_events: list[TriggeredEvent],
        suppress_arrival_and_idle: bool = False,
    ) -> list[Scene]:
        scenes: list[Scene] = []
        player_moved = state.player_location != state.previous_player_location

        for event in visible_events:
            if event.event_id in state.recent_scene_event_ids:
                continue

            rp_text, observer_text = render_event_scene(event, state.tick, self.npc_names, player_moved)
            scene = Scene(
                source_event_id=event.event_id,
                tick=state.tick,
                location=event.location,
                text=rp_text,
                observer_text=observer_text,
            )
            scenes.append(scene)
            state.recent_scene_event_ids.add(event.event_id)
            state.world_log.append(f"장면 생성: {scene.text}")

        if scenes:
            return scenes

        notice_scene = self._create_notice_scene(state)
        if notice_scene is not None:
            scenes.append(notice_scene)
            state.world_log.append(f"장면 생성: {notice_scene.text}")
            return scenes

        if suppress_arrival_and_idle:
            return scenes

        arrival_scene = self._create_arrival_scene(state)
        if arrival_scene is not None:
            scenes.append(arrival_scene)
            state.world_log.append(f"장면 생성: {arrival_scene.text}")
            return scenes

        idle_scene = self._create_idle_scene_on_entry(state)
        if idle_scene is not None:
            scenes.append(idle_scene)
            state.world_log.append(f"장면 생성: {idle_scene.text}")

        return scenes

    def _create_notice_scene(self, state: WorldState) -> Scene | None:
        for notice in state.player_notices:
            if notice.created_tick != state.tick:
                continue
            if notice.location != state.player_location:
                continue
            rp_text, observer_text = render_notice_scene(notice.observer_npc_id, state.tick, self.npc_names)
            return Scene(
                source_event_id=None,
                tick=state.tick,
                location=state.player_location,
                text=rp_text,
                observer_text=observer_text,
            )
        return None

    def _create_arrival_scene(self, state: WorldState) -> Scene | None:
        if state.player_location != state.previous_player_location:
            return None

        player_location = state.player_location
        for npc_id, current_location in state.npc_locations.items():
            if npc_id not in state.previous_npc_locations:
                continue
            previous_location = state.previous_npc_locations[npc_id]
            if current_location != player_location:
                continue
            if previous_location == current_location:
                continue
            rp_text, observer_text = render_arrival_scene(player_location, npc_id, state.tick, self.npc_names)
            return Scene(
                source_event_id=None,
                tick=state.tick,
                location=player_location,
                text=rp_text,
                observer_text=observer_text,
            )
        return None

    def _create_idle_scene_on_entry(self, state: WorldState) -> Scene | None:
        if state.player_location == state.previous_player_location:
            return None

        present_npcs = [npc_id for npc_id, location in state.npc_locations.items() if location == state.player_location]
        if not present_npcs:
            return None

        location = state.player_location
        primary_npc_id = present_npcs[0]
        rp_text, observer_text = render_idle_scene(location, primary_npc_id, state.tick, self.npc_names)

        return Scene(
            source_event_id=None,
            tick=state.tick,
            location=location,
            text=rp_text,
            observer_text=observer_text,
        )
