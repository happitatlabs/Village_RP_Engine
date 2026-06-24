from __future__ import annotations

from collections import deque

from village_rp_engine.core.mode_controller import build_engine, build_world_engine, create_default_state, create_default_world_snapshot
import village_rp_engine.core.world_engine as world_engine_module
from village_rp_engine.core.world_engine import build_world_snapshot, can_travel_between_settlements, save_world_state_to_slot
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.phase1_world import SettlementLink
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.main import prompt_player_action
from web_ui import HTML_PAGE, EngineSession, build_action, serialize_snapshot, serialize_state


def test_build_action_supports_wait_move_talk() -> None:
    assert build_action({'action_type': 'wait'}) == PlayerAction.wait()
    assert build_action({'action_type': 'move', 'target_location': '술집'}) == PlayerAction.move('술집')
    assert build_action({'action_type': 'talk', 'target_npc_id': 'farmer'}) == PlayerAction.talk('farmer')
    assert build_action({'action_type': 'travel', 'target_settlement_id': 'village_2'}) == PlayerAction.travel('village_2')


def test_serialize_state_includes_present_npcs_and_logs() -> None:
    engine = build_engine()
    state = create_default_state()
    state.npc_locations = engine.movement_system.resolve_locations_for_phase(state.time_phase)

    payload = serialize_state(state)

    assert payload['player_location'] == state.player_location
    assert any(npc['npc_id'] == 'farmer' for npc in payload['present_npcs'])
    assert 'npc_status_lines' in payload
    assert 'quests' in payload
    assert 'player_relationships' in payload
    assert payload['visible_scenes'] == []


def test_demo_and_web_ui_still_use_rp_surface() -> None:
    session = EngineSession()

    assert session.snapshot_state.simulation_depth.name == 'ACTIVE'
    assert session.snapshot_state.presentation_state.present_npcs

    status, payload = session.apply_action({'action_type': 'wait'})

    assert status == 200
    assert 'visible_scenes' in payload
    assert 'world_log' in payload


def test_serialize_snapshot_uses_derived_presentation_state() -> None:
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.wait())

    payload = serialize_snapshot(snapshot)

    assert payload['world_log'] == list(snapshot.presentation_state.world_log_lines)
    assert payload['relationships'] == list(snapshot.presentation_state.relationship_lines)
    assert payload['active_settlement_id'] == snapshot.active_settlement_id
    assert payload['available_settlements']


def test_web_ui_script_renders_valid_join_expression() -> None:
    assert HTML_PAGE.count("join('\\n')") >= 4
    assert "join('`n')" not in HTML_PAGE


def test_cli_and_web_ui_share_same_travel_legality_rule() -> None:
    snapshot = create_default_world_snapshot()
    snapshot = build_world_snapshot(
        settlement_definitions=snapshot.settlement_definitions,
        settlement_states=snapshot.settlement_states,
        active_settlement_id=snapshot.active_settlement_id,
        recently_visited_ids=snapshot.recently_visited_ids,
        settlement_links=(SettlementLink('village_1', 'village_2', 'road', 1, 1, 1),),
    )
    cli_travel_targets = [
        settlement_id
        for settlement_id in snapshot.settlement_definitions
        if can_travel_between_settlements(snapshot.active_settlement_id, settlement_id, snapshot.settlement_links)
    ]
    web_payload = serialize_snapshot(snapshot)
    outputs: list[str] = []
    inputs = deque(['travel town_1', 'travel village_2'])

    action = prompt_player_action(
        [location for location in snapshot.settlement_definition.locations if location != '집'],
        list(snapshot.settlement_definition.npc_ids),
        current_location=snapshot.settlement_state.player_location,
        travel_targets=cli_travel_targets,
        input_func=lambda _: inputs.popleft(),
        output_func=outputs.append,
    )

    assert web_payload['available_settlements'] == cli_travel_targets
    assert action == PlayerAction.travel('village_2')
    assert any('이동할 수 없는 정착지입니다.' in line for line in outputs)


def test_web_ui_recent_save_list_is_exposed_at_top(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(world_engine_module, 'SAVE_DIR', tmp_path / 'saves')
    snapshot = create_default_world_snapshot()
    save_world_state_to_slot(snapshot, 3)

    payload = serialize_snapshot(snapshot)

    assert 'recent_saves' in payload
    assert payload['recent_saves']
    assert payload['recent_saves'][0]['slot'] == 3
    assert 'id="recentSaves"' in HTML_PAGE


def test_serialize_snapshot_includes_facility_surface() -> None:
    snapshot = create_default_world_snapshot()

    payload = serialize_snapshot(snapshot)

    assert payload['selected_facility_id'] == 'square'
    assert any(facility['facility_id'] == 'tavern' for facility in payload['facilities'])
    assert payload['facility_view']['title'] == '광장'
    assert 'cards' in payload['facility_view']
    assert 'npc_cards' in payload['facility_view']
    assert payload['settlement_flavor_title'] == '회색언덕 마을'
    assert any('에단이 쓰러져 있던 너를 회색언덕으로 데려왔다.' in line for card in payload['facility_view']['cards'] for line in card['lines'])


def test_web_ui_facility_surface_differs_by_settlement_flavor() -> None:
    session = EngineSession()

    village_payload = serialize_snapshot(session.snapshot_state)
    assert not any(facility['facility_id'] == 'market' for facility in village_payload['facilities'])
    assert village_payload['settlement_flavor_title'] == '회색언덕 마을'

    session.snapshot_state = session.world_engine.run_step(session.snapshot_state, Mode.RP, action=PlayerAction.travel('village_2'))
    village_2_payload = serialize_snapshot(session.snapshot_state, selected_facility_id='clinic')
    assert any(facility['facility_id'] == 'clinic' for facility in village_2_payload['facilities'])
    assert village_2_payload['facility_view']['title'] == '치료소'
    assert '여행자와 피난민' in village_2_payload['settlement_flavor_title']

    session.snapshot_state = session.world_engine.run_step(session.snapshot_state, Mode.RP, action=PlayerAction.travel('town_1'))
    town_payload = serialize_snapshot(session.snapshot_state, selected_facility_id='market')
    assert any(facility['facility_id'] == 'market' for facility in town_payload['facilities'])
    assert town_payload['facility_view']['title'] == '시장'
    assert '상업 중심' in town_payload['settlement_flavor_title']


def test_web_ui_archive_surface_exposes_mvp_recording_frame() -> None:
    snapshot = create_default_world_snapshot()

    payload = serialize_snapshot(snapshot, selected_facility_id='archive')

    assert payload['facility_view']['title'] == '기록관'
    assert any(card['title'] == '기록자의 첫 장' for card in payload['facility_view']['cards'])


def test_engine_session_keeps_facility_on_load_and_resets_to_square(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(world_engine_module, 'SAVE_DIR', tmp_path / 'saves')
    session = EngineSession()

    status, payload = session.apply_action({'action_type': 'select_facility', 'facility_id': 'archive'})
    assert status == 200
    assert payload['selected_facility_id'] == 'archive'

    session.save(1)
    status, payload = session.load(1)
    assert status == 200
    assert payload['selected_facility_id'] == 'archive'

    payload = session.reset()
    assert payload['selected_facility_id'] == 'square'
