from __future__ import annotations

from village_rp_engine.config import MEDIATE_TAVERN_CONFLICT_QUEST_ID, PLAYER_RELATIONSHIP_NPC_IDS
from village_rp_engine.core.mode_controller import build_engine, create_default_state, run_mode_tick
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.npc_state import NPCRecentState
from village_rp_engine.models.player_action import PlayerAction


def test_player_relationships_initialized() -> None:
    state = create_default_state()

    assert state.player_relationships == {npc_id: 0 for npc_id in PLAYER_RELATIONSHIP_NPC_IDS}


def test_village_elder_can_activate_mediation_quest() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "아침"
    state.npc_locations = {
        "blacksmith": "광장",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "광장",
        "guard_captain": "광장",
    }
    state.npc_recent_states = {
        "farmer": [
            NPCRecentState(
                npc_id="farmer",
                state_id="complaining_about_blacksmith",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ],
        "blacksmith": [
            NPCRecentState(
                npc_id="blacksmith",
                state_id="irritated_with_farmer",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ],
    }

    state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda: PlayerAction.talk("village_elder"))

    assert state.quest_status[MEDIATE_TAVERN_CONFLICT_QUEST_ID] == "active"
    assert state.player_relationships["village_elder"] == 1
    assert state.dialogues[-1].text == "작은 다툼도 오래 두면 마을을 흐리네. 자네가 한번 말을 붙여보게."


def test_mediation_quest_completion_updates_player_relationships() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "새벽"
    state.npc_locations = {
        "blacksmith": "광장",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "광장",
        "guard_captain": "광장",
    }
    state.npc_recent_states = {
        "farmer": [
            NPCRecentState(
                npc_id="farmer",
                state_id="complaining_about_blacksmith",
                source_event_id="argument_at_tavern",
                expires_day=1,
            )
        ],
        "blacksmith": [
            NPCRecentState(
                npc_id="blacksmith",
                state_id="irritated_with_farmer",
                source_event_id="argument_at_tavern",
                expires_day=1,
            )
        ],
    }

    state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda: PlayerAction.talk("village_elder"))
    state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda: PlayerAction.talk("farmer"))
    state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda: PlayerAction.talk("blacksmith"))
    state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda: PlayerAction.wait())

    assert state.quest_status[MEDIATE_TAVERN_CONFLICT_QUEST_ID] == "completed"
    assert state.player_relationships["village_elder"] == 2
    assert state.player_relationships["farmer"] == 1
    assert state.player_relationships["blacksmith"] == 1


def test_quest_status_persists_in_world_state() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "아침"
    state.npc_locations = {
        "blacksmith": "광장",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "광장",
        "guard_captain": "광장",
    }
    state.npc_recent_states = {
        "farmer": [
            NPCRecentState(
                npc_id="farmer",
                state_id="complaining_about_blacksmith",
                source_event_id="argument_at_tavern",
                expires_day=3,
            )
        ],
        "blacksmith": [
            NPCRecentState(
                npc_id="blacksmith",
                state_id="irritated_with_farmer",
                source_event_id="argument_at_tavern",
                expires_day=3,
            )
        ],
    }

    state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda: PlayerAction.talk("village_elder"))
    assert state.quest_status[MEDIATE_TAVERN_CONFLICT_QUEST_ID] == "active"

    state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda: PlayerAction.move("술집"))
    assert state.quest_status[MEDIATE_TAVERN_CONFLICT_QUEST_ID] == "active"
