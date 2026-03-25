from __future__ import annotations

from village_rp_engine.core.mode_controller import build_world_engine, create_default_world_snapshot
from village_rp_engine.core.world_engine import load_world_state, reset_world_to_seed, save_world_state
from village_rp_engine.logs.chronicle import build_chronicle_query
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.player_action import PlayerAction


def _wait_ticks(world, snapshot, count: int):
    for _ in range(count):
        snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    return snapshot


def test_player_choice_emits_influence_not_direct_mutation() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    before = (snapshot.settlement_state.security, snapshot.settlement_state.stress, dict(snapshot.settlement_state.economy_profile))

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.choose('support_guard'))

    assert (snapshot.settlement_state.security, snapshot.settlement_state.stress, dict(snapshot.settlement_state.economy_profile)) == before
    assert any(influence.player_driven and influence.choice_id == 'support_guard' for influence in snapshot.pending_influences)


def test_delayed_choice_consequence_applies_on_later_tick() -> None:
    world = build_world_engine()
    control = create_default_world_snapshot()
    chosen = create_default_world_snapshot()

    chosen = world.run_step(chosen, Mode.RP, action=PlayerAction.choose('support_guard'))

    control = world.run_step(control, Mode.RP, action=PlayerAction.wait())
    chosen = world.run_step(chosen, Mode.RP, action=PlayerAction.wait())
    assert chosen.settlement_state.security == control.settlement_state.security

    control = world.run_step(control, Mode.RP, action=PlayerAction.wait())
    chosen = world.run_step(chosen, Mode.RP, action=PlayerAction.wait())
    assert chosen.settlement_state.security == control.settlement_state.security + 1


def test_special_npc_not_encountered_immediately() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.choose('follow_whisper'))

    assert snapshot.special_npc_states['wandering_stranger'].status == 'DORMANT'
    assert not any('수상한 나그네' in dialogue.text for dialogue in snapshot.presentation_state.dialogues)


def test_special_npc_eventual_encounter_after_conditions() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.choose('follow_whisper'))
    snapshot = _wait_ticks(world, snapshot, 3)
    assert snapshot.special_npc_states['wandering_stranger'].status == 'LINKED'

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.choose('support_guard'))
    snapshot = _wait_ticks(world, snapshot, 2)
    assert snapshot.special_npc_states['wandering_stranger'].status == 'CONVERGING'

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    assert snapshot.special_npc_states['wandering_stranger'].status == 'CONVERGING'

    snapshot = _wait_ticks(world, snapshot, 2)

    assert snapshot.special_npc_states['wandering_stranger'].status == 'ENCOUNTERED'
    assert any(dialogue.speaker_id == 'wandering_stranger' for dialogue in snapshot.presentation_state.dialogues)


def test_chronicle_links_choice_and_delayed_outcome() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.choose('support_guard'))
    snapshot = _wait_ticks(world, snapshot, 2)
    entries = build_chronicle_query(snapshot).query_entries(keyword='경계', limit=20).entries

    assert any('경계 근처에 조용한 호의가 남았다.' == entry.text for entry in entries)
    assert any('경계 쪽의 공기가 조금 더 단단해졌다.' == entry.text for entry in entries)


def test_chronicle_choice_trace_is_not_overly_explanatory() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.choose('support_guard'))
    snapshot = _wait_ticks(world, snapshot, 2)
    entries = build_chronicle_query(snapshot).query_entries(keyword='경계', limit=20).entries

    assert entries
    assert all('support_guard' not in entry.text for entry in entries)
    assert all('choice:' not in entry.text for entry in entries)
    assert all('security' not in entry.text for entry in entries)
    assert all('stress' not in entry.text for entry in entries)
    assert all('economy' not in entry.text for entry in entries)


def test_special_npc_encounter_requires_context_not_just_timer() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.choose('follow_whisper'))
    snapshot = _wait_ticks(world, snapshot, 3)
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.choose('support_guard'))
    snapshot = _wait_ticks(world, snapshot, 2)

    assert snapshot.special_npc_states['wandering_stranger'].status == 'CONVERGING'
    assert snapshot.settlement_state.time_phase == '아침'

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    assert snapshot.settlement_state.time_phase == '낮'
    assert snapshot.special_npc_states['wandering_stranger'].status == 'CONVERGING'
    assert not any(dialogue.speaker_id == 'wandering_stranger' for dialogue in snapshot.presentation_state.dialogues)


def test_save_load_preserves_interaction_runtime_state() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.choose('follow_whisper'))
    snapshot = _wait_ticks(world, snapshot, 3)

    saved_data = save_world_state(snapshot)
    loaded = load_world_state(
        saved_data,
        settlement_definitions=world.settlement_definitions,
        settlement_links=world.settlement_links,
        region_definitions=world.region_definitions,
        continent_definitions=world.continent_definitions,
    )

    assert loaded.pending_influences == snapshot.pending_influences
    assert loaded.interaction_runtime_state == snapshot.interaction_runtime_state
    assert loaded.special_npc_states == snapshot.special_npc_states


def test_reset_clears_interaction_runtime_state() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.choose('follow_whisper'))

    reset_snapshot = reset_world_to_seed(world)

    assert snapshot.pending_influences
    assert reset_snapshot.pending_influences == ()
    assert reset_snapshot.interaction_runtime_state.choice_counts == {}
    assert reset_snapshot.interaction_runtime_state.last_choice_id is None
    assert reset_snapshot.special_npc_states['wandering_stranger'].status == 'DORMANT'


def test_save_load_preserves_remaining_delay_ticks_mid_countdown() -> None:
    world = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.choose('ignore_murmurs'))
    snapshot = world.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    saved_data = save_world_state(snapshot)
    loaded = load_world_state(
        saved_data,
        settlement_definitions=world.settlement_definitions,
        settlement_links=world.settlement_links,
        region_definitions=world.region_definitions,
        continent_definitions=world.continent_definitions,
    )

    assert any(influence.choice_id == 'ignore_murmurs' and influence.delay_ticks == 1 for influence in loaded.pending_influences)

    loaded = world.run_step(loaded, Mode.RP, action=PlayerAction.wait())
    assert any(influence.choice_id == 'ignore_murmurs' and influence.delay_ticks == 0 for influence in loaded.pending_influences)
    assert not any('선택의 여파 [choice:ignore_murmurs]' in line for line in loaded.settlement_state.world_log)

    loaded = world.run_step(loaded, Mode.RP, action=PlayerAction.wait())
    assert not any(influence.choice_id == 'ignore_murmurs' for influence in loaded.pending_influences)
    assert any('선택의 여파 [choice:ignore_murmurs]' in line for line in loaded.settlement_state.world_log)
