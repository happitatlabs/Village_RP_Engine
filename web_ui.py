from __future__ import annotations

import argparse
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from village_rp_engine.core.mode_controller import build_world_engine, create_default_world_snapshot, run_mode_step
from village_rp_engine.logs.chronicle import (
    build_chronicle_query,
    build_world_summary_snapshot,
    compare_continents,
    compare_regions,
    compare_settlements,
    get_player_timeline,
)
from village_rp_engine.core.world_engine import (
    build_world_snapshot,
    can_travel_between_settlements,
    get_player_interaction_choices,
    list_recent_save_slots,
    load_world_state_from_slot,
    reset_world_to_seed,
    save_world_state_to_slot,
)
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.phase1_world import WorldSnapshot
from village_rp_engine.models.player_action import PlayerAction


HTML_PAGE = r"""
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Village RP Engine MVP UI</title>
  <style>
    :root {
      --bg: #111315;
      --panel: #171a1d;
      --panel-2: #1e2328;
      --line: #2f363d;
      --text: #e7e1d6;
      --muted: #a7a093;
      --accent: #c6b07a;
      --danger: #d08f7c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: linear-gradient(180deg, #0f1113 0%, #15181b 100%);
      color: var(--text);
      font: 15px/1.5 Georgia, "Times New Roman", serif;
    }
    .app {
      max-width: 1100px;
      margin: 0 auto;
      padding: 20px;
      display: grid;
      gap: 16px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 16px;
    }
    .summary {
      display: flex;
      flex-wrap: wrap;
      gap: 12px 24px;
      align-items: baseline;
    }
    .summary strong {
      color: var(--accent);
      font-size: 20px;
      font-weight: normal;
    }
    .grid {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 16px;
    }
    .section { margin-bottom: 14px; }
    .section:last-child { margin-bottom: 0; }
    h1, h2, h3 {
      margin: 0 0 10px;
      font-weight: normal;
      letter-spacing: 0.02em;
    }
    h1 { font-size: 22px; }
    h2 { font-size: 17px; color: var(--accent); }
    h3 { font-size: 15px; color: var(--muted); }
    ul {
      margin: 0;
      padding-left: 18px;
    }
    li { margin-bottom: 4px; }
    .empty { color: var(--muted); }
    .controls { display: grid; gap: 14px; }
    .button-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    button {
      background: var(--panel-2);
      color: var(--text);
      border: 1px solid var(--line);
      padding: 8px 12px;
      cursor: pointer;
      font: inherit;
    }
    button:hover { border-color: var(--accent); }
    button.secondary { color: var(--muted); }
    .hint {
      color: var(--muted);
      font-size: 13px;
    }
    details {
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }
    summary {
      cursor: pointer;
      color: var(--accent);
      margin-bottom: 8px;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font: 13px/1.45 Consolas, monospace;
      color: #d8d2c5;
    }
    .npc-list {
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 13px;
    }
    .error {
      color: var(--danger);
      font-size: 13px;
      min-height: 18px;
    }
    @media (max-width: 820px) {
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app">
    <div class="panel">
      <h1>Village RP Engine MVP UI</h1>
      <div class="summary">
        <div><strong id="dayTick">Day 1 | Tick 0 | 아침</strong></div>
        <div>현재 정착지: <span id="activeSettlement">village_1</span></div>
        <div>현재 위치: <span id="playerLocation">광장</span></div>
        <div>Mode: <span>RP</span></div>
      </div>
      <div class="section">
        <h2>최근 저장 목록</h2>
        <ul id="recentSaves"></ul>
      </div>
    </div>

    <div class="grid">
      <div class="panel">
        <div class="section">
          <h2>Visible Scenes</h2>
          <ul id="scenes"></ul>
        </div>
        <div class="section">
          <h2>Dialogues</h2>
          <ul id="dialogues"></ul>
        </div>
        <div class="section">
          <h2>발생 이벤트</h2>
          <ul id="events"></ul>
        </div>
        <div class="section">
          <h2>Rumor 요약</h2>
          <ul id="rumors"></ul>
        </div>
        <div class="section">
          <h2>Quest</h2>
          <ul id="quests"></ul>
        </div>
        <div class="section">
          <h2>Favor</h2>
          <ul id="playerRelationships"></ul>
        </div>
        <div class="section">
          <h2>Relationships</h2>
          <ul id="relationships"></ul>
        </div>
      </div>

      <div class="controls">
        <div class="panel">
          <h2>행동</h2>
          <div class="section">
            <h3>대기</h3>
            <div class="button-row">
              <button data-action="wait">대기</button>
              <button class="secondary" id="saveButton">저장</button>
              <button class="secondary" id="loadButton">불러오기</button>
              <button class="secondary" id="resetButton">리셋</button>
            </div>
          </div>
          <div class="section">
            <h3>정착지 이동</h3>
            <div class="button-row" id="travelButtons"></div>
          </div>
          <div class="section">
            <h3>위치 이동</h3>
            <div class="button-row" id="moveButtons"></div>
          </div>
          <div class="section">
            <h3>대화 가능 인물</h3>
            <div class="button-row" id="talkButtons"></div>
            <div class="npc-list" id="presentNpcs"></div>
          </div>
          <div class="section">
            <h3>선택</h3>
            <div class="button-row" id="choiceButtons"></div>
            <div class="npc-list" id="specialNpcState"></div>
          </div>
          <div class="error" id="errorText"></div>
          <div class="hint">ACTIVE settlement만 장면과 대화를 렌더링하고, 다른 settlement는 경량 업데이트만 수행한다.</div>
        </div>

        <div class="panel">
          <details open>
            <summary>World Log</summary>
            <pre id="worldLog"></pre>
          </details>
          <details>
            <summary>Rumor Log</summary>
            <pre id="rumorLog"></pre>
          </details>
          <details>
            <summary>NPC 위치 / 상태</summary>
            <pre id="npcStateLog"></pre>
          </details>
          <details>
            <summary>Chronicle</summary>
            <pre id="chronicleLog"></pre>
          </details>
        </div>
      </div>
    </div>
  </div>

  <script>
    const moveButtons = document.getElementById('moveButtons');
    const travelButtons = document.getElementById('travelButtons');
    const talkButtons = document.getElementById('talkButtons');
    const choiceButtons = document.getElementById('choiceButtons');
    const presentNpcs = document.getElementById('presentNpcs');
    const specialNpcState = document.getElementById('specialNpcState');
    const errorText = document.getElementById('errorText');

    function renderList(id, items, formatter) {
      const target = document.getElementById(id);
      target.innerHTML = '';
      if (!items || items.length === 0) {
        const li = document.createElement('li');
        li.className = 'empty';
        li.textContent = '없음';
        target.appendChild(li);
        return;
      }
      for (const item of items) {
        const li = document.createElement('li');
        li.textContent = formatter ? formatter(item) : item;
        target.appendChild(li);
      }
    }

    function renderState(data) {
      document.getElementById('dayTick').textContent = `Day ${data.day} | Tick ${data.tick} | ${data.time_phase}`;
      document.getElementById('activeSettlement').textContent = data.active_settlement_id;
      document.getElementById('playerLocation').textContent = data.player_location;
      renderList('scenes', data.visible_scenes);
      renderList('dialogues', data.dialogues, (item) => `${item.speaker_name}: "${item.text}"`);
      renderList('events', data.triggered_events, (item) => item.outcome_text);
      renderList('rumors', data.rumor_lines);
      renderList('quests', data.quests);
      renderList('playerRelationships', data.player_relationships);
      renderList('relationships', data.relationships);
      renderList('recentSaves', data.recent_saves, (item) => `슬롯 ${item.slot} | Day ${item.day} Tick ${item.tick} | ${item.active_settlement_id} | ${item.saved_at}`);

      document.getElementById('worldLog').textContent = data.world_log.join('\n');
      document.getElementById('rumorLog').textContent = data.rumor_lines.join('\n') || '없음';
      document.getElementById('npcStateLog').textContent = data.npc_status_lines.join('\n');
      document.getElementById('chronicleLog').textContent = data.chronicle_lines.join('\n');

      travelButtons.innerHTML = '';
      for (const settlementId of data.available_settlements) {
        const button = document.createElement('button');
        button.textContent = settlementId;
        button.onclick = () => performAction({ action_type: 'travel', target_settlement_id: settlementId, travel_mode: 'walk' });
        travelButtons.appendChild(button);
      }

      moveButtons.innerHTML = '';
      for (const location of data.available_locations) {
        const button = document.createElement('button');
        button.textContent = location;
        button.onclick = () => performAction({ action_type: 'move', target_location: location });
        moveButtons.appendChild(button);
      }

      talkButtons.innerHTML = '';
      choiceButtons.innerHTML = '';
      presentNpcs.innerHTML = '';
      specialNpcState.innerHTML = '';
      for (const choice of data.interaction_choices) {
        const button = document.createElement('button');
        button.textContent = choice.label;
        button.onclick = () => performAction({ action_type: 'choose', choice_id: choice.choice_id });
        choiceButtons.appendChild(button);
      }
      for (const line of data.special_npc_state_lines) {
        const item = document.createElement('div');
        item.textContent = line;
        specialNpcState.appendChild(item);
      }

      if (data.present_npcs.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.textContent = '이곳에 대화 가능한 NPC가 없다.';
        presentNpcs.appendChild(empty);
      } else {
        for (const npc of data.present_npcs) {
          const button = document.createElement('button');
          button.textContent = `대화: ${npc.name}`;
          button.onclick = () => performAction({ action_type: 'talk', target_npc_id: npc.npc_id });
          talkButtons.appendChild(button);

          const line = document.createElement('div');
          line.textContent = `${npc.name} (${npc.npc_id})`;
          presentNpcs.appendChild(line);
        }
      }
    }

    async function loadState() {
      const response = await fetch('/api/state');
      const data = await response.json();
      renderState(data);
    }

    async function performAction(payload) {
      errorText.textContent = '';
      const response = await fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        errorText.textContent = data.error || '요청 처리 중 오류가 발생했다.';
        return;
      }
      renderState(data);
    }

    document.querySelector('[data-action="wait"]').onclick = () => performAction({ action_type: 'wait' });
    document.getElementById('saveButton').onclick = async () => {
      const rawSlot = window.prompt('저장 슬롯을 입력하세요. (1-3)', '1');
      if (!rawSlot) {
        return;
      }
      const slot = Number(rawSlot);
      const response = await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slot }),
      });
      const data = await response.json();
      if (!response.ok) {
        errorText.textContent = data.error || '저장 중 오류가 발생했다.';
        return;
      }
      renderState(data);
    };
    document.getElementById('loadButton').onclick = async () => {
      const rawSlot = window.prompt('불러올 슬롯을 입력하세요. (1-3)', '1');
      if (!rawSlot) {
        return;
      }
      const slot = Number(rawSlot);
      const response = await fetch('/api/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slot }),
      });
      const data = await response.json();
      if (!response.ok) {
        errorText.textContent = data.error || '불러오기 중 오류가 발생했다.';
        return;
      }
      renderState(data);
    };
    document.getElementById('resetButton').onclick = async () => {
      errorText.textContent = '';
      const response = await fetch('/api/reset', { method: 'POST' });
      const data = await response.json();
      renderState(data);
    };

    loadState();
  </script>
</body>
</html>
"""


class EngineSession:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.world_engine = build_world_engine()
        self.snapshot_state = create_default_world_snapshot()

    def reset(self) -> dict[str, Any]:
        with self._lock:
            self.snapshot_state = reset_world_to_seed(self.world_engine)
            return serialize_snapshot(self.snapshot_state)

    def save(self, slot: int) -> tuple[int, dict[str, Any]]:
        with self._lock:
            try:
                save_world_state_to_slot(self.snapshot_state, slot)
            except Exception:
                return HTTPStatus.BAD_REQUEST, {'error': '유효한 저장 슬롯(1-3)이 필요하다.'}
            return HTTPStatus.OK, serialize_snapshot(self.snapshot_state)

    def load(self, slot: int) -> tuple[int, dict[str, Any]]:
        with self._lock:
            try:
                self.snapshot_state = load_world_state_from_slot(
                    slot,
                    settlement_definitions=self.world_engine.settlement_definitions,
                    settlement_links=self.world_engine.settlement_links,
                    region_definitions=self.world_engine.region_definitions,
                    continent_definitions=self.world_engine.continent_definitions,
                )
            except Exception:
                return HTTPStatus.BAD_REQUEST, {'error': '유효한 저장 슬롯(1-3)이 필요하다.'}
            return HTTPStatus.OK, serialize_snapshot(self.snapshot_state)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return serialize_snapshot(self.snapshot_state)

    def apply_action(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        with self._lock:
            try:
                action = build_action(payload)
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {'error': str(exc)}
            settlement_state = self.snapshot_state.settlement_state
            settlement_definition = self.snapshot_state.settlement_definition
            if action.action_type == 'move' and action.target_location == settlement_state.player_location:
                return HTTPStatus.BAD_REQUEST, {'error': f'이미 {settlement_state.player_location}에 있다.'}
            if action.action_type == 'move' and action.target_location not in settlement_definition.locations:
                return HTTPStatus.BAD_REQUEST, {'error': '이동할 수 없는 장소다.'}
            if action.action_type == 'choose' and action.choice_id not in {choice['choice_id'] for choice in get_player_interaction_choices()}:
                return HTTPStatus.BAD_REQUEST, {'error': '지원하지 않는 선택이다.'}
            if action.action_type == 'travel' and action.target_settlement_id == self.snapshot_state.active_settlement_id:
                return HTTPStatus.BAD_REQUEST, {'error': '이미 그 정착지에 있다.'}
            if action.action_type == 'travel' and not can_travel_between_settlements(
                self.snapshot_state.active_settlement_id,
                action.target_settlement_id,
                self.snapshot_state.settlement_links,
            ):
                return HTTPStatus.BAD_REQUEST, {'error': '직접 연결된 정착지로만 이동할 수 있다.'}
            self.snapshot_state = run_mode_step(
                self.world_engine,
                self.snapshot_state,
                Mode.RP,
                action_provider=lambda action=action: action,
            )
            return HTTPStatus.OK, serialize_snapshot(self.snapshot_state)


class UIRequestHandler(BaseHTTPRequestHandler):
    session = EngineSession()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == '/':
            self._send_html(HTML_PAGE)
            return
        if parsed.path == '/api/state':
            self._send_json(HTTPStatus.OK, self.session.snapshot())
            return
        self._send_json(HTTPStatus.NOT_FOUND, {'error': 'Not found'})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == '/api/reset':
            self._send_json(HTTPStatus.OK, self.session.reset())
            return
        if parsed.path == '/api/save':
            payload = self._read_json()
            slot = payload.get('slot') if payload is not None else None
            if not isinstance(slot, int):
                self._send_json(HTTPStatus.BAD_REQUEST, {'error': '유효한 저장 슬롯(1-3)이 필요하다.'})
                return
            status, body = self.session.save(slot)
            self._send_json(status, body)
            return
        if parsed.path == '/api/load':
            payload = self._read_json()
            slot = payload.get('slot') if payload is not None else None
            if not isinstance(slot, int):
                self._send_json(HTTPStatus.BAD_REQUEST, {'error': '유효한 저장 슬롯(1-3)이 필요하다.'})
                return
            status, body = self.session.load(slot)
            self._send_json(status, body)
            return
        if parsed.path == '/api/action':
            payload = self._read_json()
            if payload is None:
                self._send_json(HTTPStatus.BAD_REQUEST, {'error': '잘못된 JSON 요청이다.'})
                return
            status, body = self.session.apply_action(payload)
            self._send_json(status, body)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {'error': 'Not found'})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json(self) -> dict[str, Any] | None:
        try:
            content_length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return None
        raw = self.rfile.read(content_length)
        try:
            data = json.loads(raw.decode('utf-8'))
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _send_html(self, html: str) -> None:
        encoded = html.encode('utf-8')
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def build_action(payload: dict[str, Any]) -> PlayerAction:
    action_type = payload.get('action_type')
    if action_type == 'wait':
        return PlayerAction.wait()
    if action_type == 'move':
        target_location = payload.get('target_location')
        if not isinstance(target_location, str):
            raise ValueError('이동할 수 없는 장소다.')
        return PlayerAction.move(target_location)
    if action_type == 'talk':
        target_npc_id = payload.get('target_npc_id')
        if not isinstance(target_npc_id, str):
            raise ValueError('대화할 수 없는 대상이다.')
        return PlayerAction.talk(target_npc_id)
    if action_type == 'choose':
        choice_id = payload.get('choice_id')
        if not isinstance(choice_id, str):
            raise ValueError('선택할 수 없는 행동이다.')
        return PlayerAction.choose(choice_id)
    if action_type == 'travel':
        target_settlement_id = payload.get('target_settlement_id')
        if not isinstance(target_settlement_id, str):
            raise ValueError('이동할 수 없는 정착지다.')
        travel_mode = payload.get('travel_mode', 'walk')
        if not isinstance(travel_mode, str):
            raise ValueError('이동할 수 없는 정착지다.')
        return PlayerAction.travel(target_settlement_id, travel_mode=travel_mode)
    raise ValueError('지원하지 않는 행동이다.')


def serialize_snapshot(snapshot: WorldSnapshot) -> dict[str, Any]:
    settlement_state = snapshot.settlement_state
    settlement_definition = snapshot.settlement_definition
    presentation_state = snapshot.presentation_state
    chronicle_query = build_chronicle_query(snapshot)
    world_summary = build_world_summary_snapshot(snapshot)
    player_timeline = get_player_timeline(snapshot, limit=4)
    active_region_id = settlement_definition.region_id
    active_region_definition = snapshot.region_definitions.get(active_region_id)
    active_continent_id = active_region_definition.continent_id if active_region_definition is not None else None
    available_locations = [location for location in settlement_definition.locations if location != '집']
    available_settlements = [
        settlement_id
        for settlement_id in snapshot.settlement_definitions
        if can_travel_between_settlements(snapshot.active_settlement_id, settlement_id, snapshot.settlement_links)
    ]
    recent_result = chronicle_query.query_entries(limit=5)
    settlement_result = chronicle_query.query_entries(settlement_id=snapshot.active_settlement_id, limit=4)
    region_result = chronicle_query.query_entries(region_id=active_region_id, limit=4)
    comparison_targets = [snapshot.active_settlement_id]
    comparison_targets.extend(
        settlement_id for settlement_id in snapshot.settlement_definitions
        if settlement_id != snapshot.active_settlement_id
    )
    comparison_result = compare_settlements(snapshot, comparison_targets[:2])
    region_ids = list(snapshot.region_definitions)
    region_comparison_result = compare_regions(snapshot, region_ids[:2])
    continent_ids = list(snapshot.continent_definitions)
    continent_comparison_result = compare_continents(snapshot, continent_ids[:2] or continent_ids)
    recent_saves = list_recent_save_slots()
    interaction_choices = list(get_player_interaction_choices())
    special_npc_state_lines = [
        f"{npc_id}: {state.status} ({state.linked_settlement_id or 'unlinked'})"
        for npc_id, state in sorted(snapshot.special_npc_states.items())
    ]
    history_surface = {
        'recent': {
            'total_count': recent_result.total_count,
            'entries': [
                {'day': entry.day, 'tick': entry.tick, 'category': entry.category, 'text': entry.text}
                for entry in recent_result.entries
            ],
        },
        'settlement': {
            'scope_id': snapshot.active_settlement_id,
            'entries': [
                {'day': entry.day, 'tick': entry.tick, 'category': entry.category, 'text': entry.text}
                for entry in settlement_result.entries
            ],
        },
        'region': {
            'scope_id': active_region_id,
            'entries': [
                {'day': entry.day, 'tick': entry.tick, 'category': entry.category, 'text': entry.text}
                for entry in region_result.entries
            ],
        },
        'comparison': {
            'scope_type': comparison_result.scope_type,
            'summary_lines': list(comparison_result.summary_lines),
        },
        'region_comparison': {
            'scope_type': region_comparison_result.scope_type,
            'summary_lines': list(region_comparison_result.summary_lines),
        },
        'continent_comparison': {
            'scope_type': continent_comparison_result.scope_type,
            'summary_lines': list(continent_comparison_result.summary_lines),
        },
        'player_timeline': [
            {
                'day': item.entry.day,
                'tick': item.entry.tick,
                'text': item.entry.text,
                'direct': item.direct,
                'perspective': item.perspective,
            }
            for item in player_timeline
        ],
    }
    chronicle_lines = [
        '[Recent World Changes]',
        *[f"Day {entry['day']} Tick {entry['tick']} | {entry['category']} | {entry['text']}" for entry in history_surface['recent']['entries']],
        '',
        '[Player Timeline]',
        *[f"Day {entry['day']} Tick {entry['tick']} | {entry['perspective']} | {entry['text']}" for entry in history_surface['player_timeline']],
        '',
        '[Active Settlement History]',
        *[f"Day {entry['day']} Tick {entry['tick']} | {entry['category']} | {entry['text']}" for entry in history_surface['settlement']['entries']],
        '',
        '[Region History]',
        *([*world_summary.region_summaries[:2], *[f"Day {entry['day']} Tick {entry['tick']} | {entry['category']} | {entry['text']}" for entry in history_surface['region']['entries']]] or ['없음']),
        '',
        '[Settlement Comparison]',
        *(history_surface['comparison']['summary_lines'] or ['없음']),
        '',
        '[Region Comparison]',
        *(history_surface['region_comparison']['summary_lines'] or ['없음']),
        '',
        '[Continent Comparison]',
        *(history_surface['continent_comparison']['summary_lines'] or ['없음']),
        '',
        '[Continent]',
        *world_summary.continent_summaries[:2],
    ]
    return {
        'active_settlement_id': snapshot.active_settlement_id,
        'day': settlement_state.day,
        'tick': settlement_state.tick,
        'time_phase': settlement_state.time_phase,
        'player_location': settlement_state.player_location,
        'available_locations': available_locations,
        'available_settlements': available_settlements,
        'present_npcs': [
            {'npc_id': npc.npc_id, 'name': npc.name}
            for npc in presentation_state.present_npcs
        ],
        'visible_scenes': list(presentation_state.visible_scenes),
        'dialogues': [
            {'speaker_id': dialogue.speaker_id, 'speaker_name': dialogue.speaker_name, 'text': dialogue.text}
            for dialogue in presentation_state.dialogues
        ],
        'triggered_events': [
            {'event_id': event.event_id, 'outcome_text': event.outcome_text}
            for event in presentation_state.triggered_event_summaries
        ],
        'rumor_lines': list(presentation_state.rumor_lines),
        'quests': list(presentation_state.quest_lines),
        'player_relationships': list(presentation_state.player_relationship_lines),
        'relationships': list(presentation_state.relationship_lines),
        'world_log': list(presentation_state.world_log_lines),
        'npc_status_lines': list(presentation_state.npc_status_lines),
        'history_surface': history_surface,
        'chronicle_lines': chronicle_lines,
        'active_region_id': active_region_id,
        'active_continent_id': active_continent_id,
        'recent_saves': recent_saves,
        'interaction_choices': interaction_choices,
        'special_npc_state_lines': special_npc_state_lines,
    }


def serialize_state(state) -> dict[str, Any]:
    return serialize_snapshot(build_world_snapshot(state))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Village RP Engine minimal web UI')
    parser.add_argument('--host', default='127.0.0.1', help='바인드할 호스트')
    parser.add_argument('--port', type=int, default=8000, help='바인드할 포트')
    return parser.parse_args()


def run_server(host: str = '127.0.0.1', port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), UIRequestHandler)
    print(f'Village RP Engine MVP UI running at http://{host}:{port}')
    server.serve_forever()


if __name__ == '__main__':
    args = parse_args()
    run_server(host=args.host, port=args.port)
