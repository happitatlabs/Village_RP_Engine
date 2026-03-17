from __future__ import annotations

from village_rp_engine.core.mode_controller import build_engine, create_default_state
from village_rp_engine.models.player_action import PlayerAction
from web_ui import LOCATIONS, build_action, serialize_state


def test_build_action_supports_wait_move_talk() -> None:
    assert build_action({"action_type": "wait"}) == PlayerAction.wait()
    assert build_action({"action_type": "move", "target_location": "술집"}) == PlayerAction.move("술집")
    assert build_action({"action_type": "talk", "target_npc_id": "farmer"}) == PlayerAction.talk("farmer")


def test_serialize_state_includes_present_npcs_and_logs() -> None:
    engine = build_engine()
    state = create_default_state()
    state.npc_locations = engine.movement_system.resolve_locations_for_phase(state.time_phase)

    payload = serialize_state(state)

    assert payload["player_location"] in LOCATIONS
    assert any(npc["npc_id"] == "farmer" for npc in payload["present_npcs"])
    assert "npc_status_lines" in payload
    assert "quests" in payload
    assert "player_relationships" in payload
    assert payload["visible_scenes"] == []
