from __future__ import annotations

from collections import deque
from dataclasses import replace

from village_rp_engine.core.mode_controller import build_engine, build_world_engine, create_default_state, create_default_world_snapshot
import village_rp_engine.core.world_engine as world_engine_module
from village_rp_engine.core.world_engine import build_world_snapshot, can_travel_between_settlements, save_world_state_to_slot
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.phase1_world import ChronicleArchive, ChronicleEntry, PresentationDialogue
from village_rp_engine.models.player_notice import PlayerNotice
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

    assert any(card['title'] == '인트로' for card in payload['overview_cards'])
    assert any(card['title'] == '튜토리얼 1' for card in payload['overview_cards'])
    assert payload['selected_facility_id'] == 'square'
    assert any(facility['facility_id'] == 'tavern' for facility in payload['facilities'])
    assert payload['facility_view']['title'] == '광장'
    assert 'cards' in payload['facility_view']
    assert 'npc_cards' in payload['facility_view']
    assert any(line.startswith('분위기:') for line in payload['facility_view']['summary_lines'])
    assert all(not line.startswith('불안:') for line in payload['facility_view']['summary_lines'])
    assert payload['settlement_flavor_title'] == '회색언덕 마을'
    assert any('에단이 쓰러져 있던 너를 회색언덕으로 데려왔다.' in line for card in payload['facility_view']['cards'] for line in card['lines'])
    assert 'id="overviewCards"' in HTML_PAGE
    assert 'id="waitSection"' in HTML_PAGE
    assert HTML_PAGE.index('id="facilityTitle"') < HTML_PAGE.index('id="facilityButtons"')


def test_web_ui_errors_use_centered_guidance_popup() -> None:
    assert 'class="guidance-backdrop"' in HTML_PAGE
    assert 'id="guidancePopup"' in HTML_PAGE
    assert 'function showGuidancePopup(message)' in HTML_PAGE
    assert "showGuidancePopup(data.error || '요청 처리 중 오류가 발생했다.')" in HTML_PAGE


def test_action_panel_is_hidden_from_player_surface() -> None:
    assert '<div class="panel" id="actionPanel" hidden>' in HTML_PAGE


def test_web_ui_has_landscape_and_portrait_viewport_layout_rules() -> None:
    assert 'min-height: 100svh;' in HTML_PAGE
    assert '@media (orientation: landscape) and (max-height: 720px)' in HTML_PAGE
    assert '@media (orientation: portrait)' in HTML_PAGE
    assert '@media (max-width: 480px) and (orientation: portrait)' in HTML_PAGE


def test_tutorial_surface_progresses_through_talk_move_and_archive() -> None:
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()

    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.talk('ethan'))
    assert snapshot.interaction_runtime_state.tutorial_stage == 'visit_tavern'
    assert snapshot.interaction_runtime_state.intro_dismissed is True

    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.move('술집'))
    assert snapshot.interaction_runtime_state.tutorial_stage == 'visit_archive'
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.move('광장'))

    session = EngineSession()
    session.snapshot_state = snapshot
    session.selected_facility_id = 'square'
    status, payload = session.apply_action({'action_type': 'move', 'target_location': '기록관'})

    assert status == 200
    assert payload['selected_facility_id'] == 'archive'
    assert session.snapshot_state.interaction_runtime_state.tutorial_stage == 'wait_in_square'
    assert any(card['title'] == '튜토리얼 4' for card in payload['overview_cards'])


def test_tutorial_ethan_dialogue_points_to_tavern() -> None:
    session = EngineSession()

    status, payload = session.apply_action({'action_type': 'talk', 'target_npc_id': 'ethan'})

    assert status == 200
    situation_card = next(card for card in payload['overview_cards'] if card['title'] == '현재 상황')
    dialogue_lines = [dialogue['text'] for dialogue in payload['dialogues'] if dialogue['speaker_id'] == 'ethan']
    assert any('술집' in line for line in situation_card['lines'])
    assert any('술집' in line for line in dialogue_lines)
    assert any(card['title'] == '튜토리얼 2' for card in payload['overview_cards'])


def test_tutorial_card_disappears_after_completion() -> None:
    session = EngineSession()

    session.apply_action({'action_type': 'talk', 'target_npc_id': 'ethan'})
    session.apply_action({'action_type': 'move', 'target_location': '술집'})
    session.apply_action({'action_type': 'move', 'target_location': '광장'})
    session.apply_action({'action_type': 'move', 'target_location': '기록관'})
    session.apply_action({'action_type': 'move', 'target_location': '광장'})
    status, payload = session.apply_action({'action_type': 'wait'})

    assert status == 200
    assert session.snapshot_state.interaction_runtime_state.tutorial_completed is True
    assert all(not card['title'].startswith('튜토리얼') for card in payload['overview_cards'])


def test_square_facility_formats_notice_lines_without_notice_text_field() -> None:
    snapshot = create_default_world_snapshot()
    snapshot.settlement_state.player_notices.append(
        PlayerNotice(
            observer_npc_id='ethan',
            target_type='player',
            notice_type='noticed_player_at_dawn',
            location='광장',
            time_phase='새벽',
            created_tick=1,
            expires_tick=1,
        )
    )

    payload = serialize_snapshot(snapshot, selected_facility_id='square')

    assert any('에단이 새벽에 네 움직임을 눈여겨봤다.' == line for line in payload['facility_view']['summary_lines'])


def test_outside_facility_limits_irrelevant_control_sections() -> None:
    snapshot = create_default_world_snapshot()

    payload = serialize_snapshot(snapshot, selected_facility_id='outside')

    assert payload['ui_sections']['travel'] is True
    assert payload['ui_sections']['move'] is False
    assert payload['ui_sections']['talk'] is False
    assert payload['ui_sections']['choice'] is False


def test_interaction_choices_follow_facility_context_and_server_validation() -> None:
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.move('술집'))

    tavern_payload = serialize_snapshot(snapshot, selected_facility_id='tavern')
    assert tavern_payload['interaction_choices'] == []
    assert tavern_payload['ui_sections']['choice'] is False

    archive_payload = serialize_snapshot(snapshot, selected_facility_id='archive')
    assert archive_payload['interaction_choices'] == []
    assert archive_payload['ui_sections']['choice'] is False
    assert archive_payload['selected_facility_id'] == 'tavern'

    session = EngineSession()
    session.selected_facility_id = 'archive'
    status, payload = session.apply_action({'action_type': 'choose', 'choice_id': 'support_guard'})
    assert status == 400
    assert payload['error'] == '지원하지 않는 선택이다.'


def test_tavern_gather_info_returns_focus_card_without_region_influence_lines() -> None:
    world_engine = build_world_engine()
    session = EngineSession()
    session.snapshot_state = world_engine.run_step(session.snapshot_state, Mode.RP, action=PlayerAction.move('술집'))
    session.selected_facility_id = 'tavern'

    status, payload = session.apply_action({'action_type': 'gather_info'})

    assert status == 200
    assert payload['facility_view']['cards'][0]['title'] == '정보 수집 결과'
    assert all('north_fields:' not in line for line in payload['facility_view']['cards'][0]['lines'])
    assert all('security' not in line and 'stress' not in line and 'economy' not in line for line in payload['facility_view']['cards'][0]['lines'])
    assert all('이벤트 발생:' not in line for line in payload['facility_view']['cards'][0]['lines'])

    status, repeated_payload = session.apply_action({'action_type': 'gather_info'})
    assert status == 200
    assert repeated_payload['facility_view']['cards'][0]['lines'] == ['더 건질 만한 새 이야기는 없어 보인다.']


def test_archive_prioritizes_story_history_over_numeric_state_dump() -> None:
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.wait())
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.move('기록관'))

    payload = serialize_snapshot(snapshot, selected_facility_id='archive')
    cards = payload['facility_view']['cards']
    story_cards = [card for card in cards if card['title'] in {'사건 기록', '소문 기록', '플레이어 행적'}]
    first_story_lines = [line for card in story_cards[:2] for line in card['lines']]

    assert any(card['title'] == '마을 현황' for card in cards)
    assert all('security' not in line and 'stress' not in line and 'economy' not in line for line in first_story_lines)


def test_player_surface_filters_raw_state_markers_from_default_cards() -> None:
    snapshot = create_default_world_snapshot()
    snapshot = build_world_engine().run_step(snapshot, Mode.RP, action=PlayerAction.move('기록관'))
    raw_entries = (
        ChronicleEntry(
            entry_type='state',
            source_id='test',
            day=1,
            tick=1,
            text='village_1: security 60, stress 20, economy grain=80, iron=10',
            settlement_id=snapshot.active_settlement_id,
            region_id=snapshot.settlement_definition.region_id,
            category='STATE_CHANGE',
        ),
        ChronicleEntry(
            entry_type='state',
            source_id='test',
            day=1,
            tick=2,
            text='north_fields: local tension increased',
            settlement_id=snapshot.active_settlement_id,
            region_id=snapshot.settlement_definition.region_id,
            category='STATE_CHANGE',
        ),
    )
    snapshot = replace(
        snapshot,
        chronicle_archive=ChronicleArchive(entries=raw_entries),
        presentation_state=replace(
            snapshot.presentation_state,
            visible_scenes=(),
            dialogues=(),
            triggered_event_summaries=(),
            rumor_lines=('STATE_CHANGE village_1: security 60 stress 20 economy grain=80',),
        ),
    )

    payload = serialize_snapshot(snapshot, selected_facility_id='archive')
    player_lines = [
        line
        for card in (*payload['overview_cards'], *payload['facility_view']['cards'])
        for line in card.get('lines', [])
    ]
    player_lines.extend(payload['chronicle_highlights'])
    player_lines.extend(payload['rumor_lines'])
    forbidden = ('security', 'stress', 'economy', 'grain=', 'iron=', 'STATE_CHANGE', 'village_1', 'north_fields')

    assert all(not any(marker in line for marker in forbidden) for line in player_lines)


def test_player_surface_localizes_settlement_ids_time_and_ticks() -> None:
    session = EngineSession()
    session.apply_action({'action_type': 'dismiss_intro'})
    session.apply_action({'action_type': 'move', 'target_location': '술집'})
    session.apply_action({'action_type': 'gather_info'})
    session.apply_action({'action_type': 'move', 'target_location': '광장'})
    session.apply_action({'action_type': 'select_facility', 'facility_id': 'outside'})
    _, payload = session.apply_action({'action_type': 'travel', 'target_settlement_id': 'town_1', 'travel_mode': 'walk'})
    _, payload = session.apply_action({'action_type': 'move', 'target_location': '시장'})

    player_lines = [
        line
        for card in (*payload['overview_cards'], *payload['facility_view']['cards'])
        for line in card.get('lines', [])
    ]
    player_lines.extend(payload['facility_view']['summary_lines'])
    player_lines.extend(payload['chronicle_highlights'])
    player_lines.extend(payload['rumor_lines'])
    forbidden = ('village_1', 'village_2', 'town_1', 'Day ', ' Tick ', '5 ticks', 'village_1에서 술집에서')

    assert payload['active_settlement_name'] == '시장마을'
    assert all(not any(marker in line for marker in forbidden) for line in player_lines)


def test_travel_options_use_display_names_but_keep_ids_for_payloads() -> None:
    payload = serialize_snapshot(create_default_world_snapshot(), selected_facility_id='outside')

    assert payload['available_settlements'] == ['village_2', 'town_1']
    assert payload['available_settlement_options'] == [
        {'settlement_id': 'village_2', 'label': '강가마을'},
        {'settlement_id': 'town_1', 'label': '시장마을'},
    ]
    outside_titles = [card['title'] for card in payload['facility_view']['cards']]
    outside_lines = [line for card in payload['facility_view']['cards'] for line in card['lines']]
    assert 'village_2' not in outside_titles
    assert 'town_1' not in outside_titles
    assert '다섯 차례 시간이 흐른다.' in outside_lines


def test_market_and_clinic_prioritize_facility_flavor() -> None:
    session = EngineSession()
    session.snapshot_state = session.world_engine.run_step(session.snapshot_state, Mode.RP, action=PlayerAction.travel('town_1'))
    session.snapshot_state = session.world_engine.run_step(session.snapshot_state, Mode.RP, action=PlayerAction.move('시장'))
    market_payload = serialize_snapshot(session.snapshot_state, selected_facility_id='market')
    market_lines = [line for card in market_payload['facility_view']['cards'] for line in card['lines']]

    assert any('곡물 가격' in line or '거래' in line or '시장세' in line for line in market_lines)
    assert all('대장장이와 농부' not in line for line in market_lines)

    session.snapshot_state = session.world_engine.run_step(session.snapshot_state, Mode.RP, action=PlayerAction.travel('village_2'))
    clinic_payload = serialize_snapshot(session.snapshot_state, selected_facility_id='clinic')
    clinic_lines = [line for card in clinic_payload['facility_view']['cards'] for line in card['lines']]

    assert any('여행자' in line or '약초' in line or '치료소' in line for line in clinic_lines)
    assert any(action['label'] == '환자 살펴보기' for action in clinic_payload['facility_view']['actions'])


def test_square_wait_action_is_not_duplicated() -> None:
    session = EngineSession()
    session.apply_action({'action_type': 'dismiss_intro'})
    session.apply_action({'action_type': 'talk', 'target_npc_id': 'ethan'})
    session.apply_action({'action_type': 'move', 'target_location': '술집'})
    session.apply_action({'action_type': 'move', 'target_location': '광장'})
    payload = session.snapshot()
    wait_labels = [action['label'] for action in payload['facility_view']['actions'] if '기다리기' in action['label']]

    assert len(wait_labels) == 1


def test_facility_hints_explain_square_only_access_from_tavern() -> None:
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()
    snapshot = world_engine.run_step(snapshot, Mode.RP, action=PlayerAction.move('술집'))

    payload = serialize_snapshot(snapshot, selected_facility_id='tavern')

    assert [facility['facility_id'] for facility in payload['facilities']] == ['square']
    assert payload['facilities'][0]['display_label'] == '광장으로 이동'
    assert payload['available_locations'] == ['광장']
    assert payload['facility_hints'] == ['다른 시설을 보려면 광장으로 돌아가야 한다.']


def test_inaccessible_location_facility_button_moves_first() -> None:
    session = EngineSession()
    session.snapshot_state = session.world_engine.run_step(session.snapshot_state, Mode.RP, action=PlayerAction.travel('town_1'))

    payload = serialize_snapshot(session.snapshot_state, selected_facility_id='square')
    market_button = next(facility for facility in payload['facilities'] if facility['facility_id'] == 'market')

    assert market_button['display_label'] == '시장으로 이동'
    assert market_button['disabled'] is False
    assert market_button['action_payload'] == {'action_type': 'move', 'target_location': '시장'}


def test_archive_and_base_facility_buttons_move_to_locations_first() -> None:
    session = EngineSession()
    payload = session.snapshot()
    archive_button = next(facility for facility in payload['facilities'] if facility['facility_id'] == 'archive')
    base_button = next(facility for facility in payload['facilities'] if facility['facility_id'] == 'base')

    assert archive_button['display_label'] == '기록관으로 이동'
    assert archive_button['action_payload'] == {'action_type': 'move', 'target_location': '기록관'}
    assert base_button['display_label'] == '거점으로 이동'
    assert base_button['action_payload'] == {'action_type': 'move', 'target_location': '거점'}

    status, archive_payload = session.apply_action(archive_button['action_payload'])
    assert status == 200
    assert archive_payload['selected_facility_id'] == 'archive'
    assert archive_payload['facility_view']['title'] == '기록관'
    assert [facility['facility_id'] for facility in archive_payload['facilities']] == ['square']

    status, _ = session.apply_action({'action_type': 'move', 'target_location': '광장'})
    assert status == 200
    base_button = next(facility for facility in session.snapshot()['facilities'] if facility['facility_id'] == 'base')
    status, base_payload = session.apply_action(base_button['action_payload'])
    assert status == 200
    assert base_payload['selected_facility_id'] == 'base'
    assert base_payload['facility_view']['title'] == '거점'
    assert any('에단' in line for line in base_payload['facility_view']['summary_lines'])
    assert any(card['title'] == '에단의 자리' for card in base_payload['facility_view']['cards'])


def test_web_ui_rejects_direct_facility_move_without_returning_to_square() -> None:
    session = EngineSession()

    status, payload = session.apply_action({'action_type': 'move', 'target_location': '기록관'})
    assert status == 200
    assert payload['selected_facility_id'] == 'archive'

    status, payload = session.apply_action({'action_type': 'move', 'target_location': '거점'})
    assert status == 400
    assert payload['error'] == '다른 시설을 보려면 먼저 광장으로 돌아가야 한다.'


def test_tavern_blocks_direct_entry_to_square_only_facilities() -> None:
    world_engine = build_world_engine()
    session = EngineSession()
    session.snapshot_state = world_engine.run_step(session.snapshot_state, Mode.RP, action=PlayerAction.move('술집'))
    session.selected_facility_id = 'tavern'

    status, payload = session.apply_action({'action_type': 'select_facility', 'facility_id': 'archive'})

    assert status == 400
    assert payload['error'] == '지금 위치에서는 그 시설로 바로 들어갈 수 없다. 먼저 광장으로 나와야 한다.'


def test_back_alley_surface_is_rumor_only_and_accessed_by_location() -> None:
    session = EngineSession()

    status, payload = session.apply_action({'action_type': 'move', 'target_location': '뒷골목'})
    assert status == 200
    assert payload['selected_facility_id'] == 'back_alley'
    assert payload['facility_view']['title'] == '뒷골목'

    status, payload = session.apply_action({'action_type': 'gather_hidden_info'})
    assert status == 200
    assert payload['facility_view']['cards'][0]['title'] == '살펴본 흔적'
    assert all('security' not in line and 'stress' not in line for line in payload['facility_view']['cards'][0]['lines'])
    assert any('골목' in line or '창고' in line or '밤' in line for line in payload['facility_view']['cards'][0]['lines'])

    status, payload = session.apply_action({'action_type': 'move', 'target_location': '광장'})
    assert status == 200
    assert payload['selected_facility_id'] == 'square'


def test_travel_returns_player_to_square_surface() -> None:
    session = EngineSession()

    status, payload = session.apply_action({'action_type': 'select_facility', 'facility_id': 'outside'})
    assert status == 200
    assert payload['selected_facility_id'] == 'outside'

    status, payload = session.apply_action({'action_type': 'travel', 'target_settlement_id': 'village_2', 'travel_mode': 'walk'})
    assert status == 200
    assert payload['selected_facility_id'] == 'square'
    assert payload['facility_view']['title'] == '광장'
    assert payload['overview_cards'][0]['subtitle'] == '이동 완료'

    payload = session.snapshot()
    assert all(card['subtitle'] != '이동 완료' for card in payload['overview_cards'])


def test_square_intro_story_card_expires_and_moves_to_archive_background() -> None:
    session = EngineSession()
    session.apply_action({'action_type': 'dismiss_intro'})
    for _ in range(4):
        session.apply_action({'action_type': 'wait'})

    payload = session.snapshot()
    assert all(card['title'] != '회색언덕의 시작' for card in payload['facility_view']['cards'])

    status, payload = session.apply_action({'action_type': 'move', 'target_location': '기록관'})
    assert status == 200
    assert payload['selected_facility_id'] == 'archive'
    assert any(card['title'] == '배경 설명' for card in payload['facility_view']['cards'])


def test_narration_is_prioritized_in_overview_and_square_cards() -> None:
    snapshot = create_default_world_snapshot()
    snapshot = replace(
        snapshot,
        presentation_state=replace(
            snapshot.presentation_state,
            visible_scenes=('광장 한복판의 공기가 무겁게 가라앉았다.',),
            dialogues=(
                PresentationDialogue(speaker_id='farmer', speaker_name='농부', text='오늘은 유난히 조용하군.'),
                PresentationDialogue(
                    speaker_id='narrator',
                    speaker_name='나레이션',
                    text='잠깐 숨을 고르자, 마을 사람들이 같은 방향을 바라보는 이유가 보였다.',
                ),
            ),
        ),
    )

    payload = serialize_snapshot(snapshot, selected_facility_id='square')
    situation_card = next(card for card in payload['overview_cards'] if card['title'] == '현재 상황')

    assert situation_card['lines'][0].startswith('나레이션:')
    assert payload['facility_view']['cards'][0]['title'] == '나레이션'


def test_situation_card_matches_current_non_square_location() -> None:
    session = EngineSession()
    status, payload = session.apply_action({'action_type': 'move', 'target_location': '뒷골목'})
    assert status == 200

    snapshot = replace(
        session.snapshot_state,
        presentation_state=replace(
            session.snapshot_state.presentation_state,
            visible_scenes=('농부가 광장에서 어젯밤 말다툼을 곱씹었다.',),
            dialogues=(PresentationDialogue(speaker_id='farmer', speaker_name='농부', text='광장 이야기가 아직 남았군.'),),
        ),
    )
    payload = serialize_snapshot(snapshot, selected_facility_id='back_alley')
    situation_card = next(card for card in payload['overview_cards'] if card['title'] == '현재 상황')
    situation_text = '\n'.join(situation_card['lines'])

    assert '골목' in situation_text
    assert '광장' not in situation_text
    assert '농부' not in situation_text


def test_system_scene_and_log_sections_are_collapsed_by_default() -> None:
    assert '<summary>시스템 보기: 장면과 대화</summary>' in HTML_PAGE
    assert '<details class="surface-detail" open>' not in HTML_PAGE
    assert '<summary>개발자 로그: World Log</summary>' in HTML_PAGE
    assert '<details open>\n            <summary>개발자 로그: World Log</summary>' not in HTML_PAGE


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
    session.snapshot_state = session.world_engine.run_step(session.snapshot_state, Mode.RP, action=PlayerAction.move('시장'))
    town_payload = serialize_snapshot(session.snapshot_state, selected_facility_id='market')
    assert town_payload['facility_view']['title'] == '시장'
    assert [facility['facility_id'] for facility in town_payload['facilities']] == ['square']
    assert '상업 중심' in town_payload['settlement_flavor_title']


def test_web_ui_archive_surface_exposes_mvp_recording_frame() -> None:
    snapshot = build_world_engine().run_step(create_default_world_snapshot(), Mode.RP, action=PlayerAction.move('기록관'))

    payload = serialize_snapshot(snapshot, selected_facility_id='archive')

    assert payload['facility_view']['title'] == '기록관'
    assert any(card['title'] == '기록자의 첫 장' for card in payload['facility_view']['cards'])


def test_engine_session_keeps_facility_on_load_and_resets_to_square(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(world_engine_module, 'SAVE_DIR', tmp_path / 'saves')
    session = EngineSession()

    status, payload = session.apply_action({'action_type': 'move', 'target_location': '기록관'})
    assert status == 200
    assert payload['selected_facility_id'] == 'archive'

    session.save(1)
    status, payload = session.load(1)
    assert status == 200
    assert payload['selected_facility_id'] == 'archive'

    payload = session.reset()
    assert payload['selected_facility_id'] == 'square'
