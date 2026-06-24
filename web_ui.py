from __future__ import annotations

import argparse
import json
import re
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
    NPC_NAME_BY_ID,
    apply_tutorial_update,
    build_world_snapshot,
    can_travel_between_settlements,
    dismiss_intro,
    list_recent_save_slots,
    load_world_state_from_slot,
    rebuild_snapshot_surface,
    reset_world_to_seed,
    save_world_state_to_slot,
)
from village_rp_engine.models.player_notice import PlayerNotice
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.phase1_world import WorldSnapshot
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.config import MEDIATE_TAVERN_CONFLICT_QUEST_ID, TIME_PHASES


DEFAULT_FACILITY_ID = 'square'
NPC_CARD_METADATA = {
    'blacksmith': {'role': '대장장이', 'personality': '완고함'},
    'farmer': {'role': '농부', 'personality': '성실함'},
    'guard_captain': {'role': '경비대장', 'personality': '신중함'},
    'innkeeper': {'role': '여관주인', 'personality': '눈치 빠름'},
    'village_elder': {'role': '촌장', 'personality': '노련함'},
    'ethan': {
        'role': '널 구해준 마을 청년',
        'personality': '고집 셈',
        'default_interest': '이방인이 된 너와 마을 주변의 낌새를 살피는 일',
    },
}

MVP_STORY_CARDS = {
    'village_1': {
        'square': {
            'title': '회색언덕의 시작',
            'subtitle': '이방인으로서 맞는 첫 하루',
            'lines': [
                '에단이 쓰러져 있던 너를 회색언덕으로 데려왔다.',
                '광장에서는 오늘의 사건과 사람들의 표정을 가장 먼저 읽을 수 있다.',
            ],
        },
        'archive': {
            'title': '기록자의 첫 장',
            'subtitle': '기록관 견습생의 시선',
            'lines': [
                '이곳에서 소문과 사건, 사람들의 흔적을 이어 하나의 기록으로 남긴다.',
                '기억의 신을 믿는 오래된 서가에는 사라지지 않아야 할 이름들이 적혀 있다.',
            ],
        },
    },
}

RUMOR_BIAS_KEYWORDS = {
    'local': ('광장', '술집', '주민', '순찰'),
    'gossip': ('소문', '이야기', '웅성'),
    'daily_life': ('농장', '수확', '아침', '저녁'),
    'refugee': ('피난', '붐비', '도착'),
    'traveler': ('여행자', '길손', '북쪽 길'),
    'recovery': ('치료', '회복', '다친'),
    'trade': ('시장', '가격', '거래'),
    'merchant': ('상인', '계약', '길드'),
    'politics': ('선출', '의견', '관리'),
}

RAW_PLAYER_SURFACE_MARKERS = (
    'security',
    'stress',
    'economy',
    'grain=',
    'iron=',
    'trade=',
    'STATE_CHANGE',
    'EVENT:',
    'mediate_tavern_conflict',
    'quest_status',
    'relation_delta',
    'resident_status',
    'recognition_score',
    'recognition_blocked_until_tick',
    'Day ',
    'Tick ',
    '5 ticks',
    'village_1',
    'village_2',
    'town_1',
    'village_1:',
    'village_2:',
    'town_1:',
    'north_fields:',
    'river_trade:',
    'continent_1:',
)

SETTLEMENT_DISPLAY_NAME_OVERRIDES = {
    'village_1': '회색언덕 마을',
    'village_2': '강가마을',
    'town_1': '시장마을',
}

SETTLEMENT_SHORT_NAME_OVERRIDES = {
    'village_1': '회색언덕',
    'village_2': '강가마을',
    'town_1': '시장마을',
}

FACILITY_RUMOR_KEYWORDS = {
    'market': ('시장', '상인', '가격', '거래', '세금', '정치', '계약', '길드', '곡물', '장터'),
    'clinic': ('치료', '회복', '여행자', '환자', '약재', '피난', '다친', '북쪽 길'),
    'tavern': ('술집', '소문', '말다툼', '여관주인', '웅성', '이야기', '언성'),
    'back_alley': ('밤', '창고', '수상', '그림자', '속삭', '숨기', '밀거래', '골목'),
}

FACILITY_DEFAULT_RUMORS = {
    'market': (
        '곡물 가격이 오를 것이라는 이야기가 돈다.',
        '북쪽 상단과 거래가 늘었다고 한다.',
        '시장세 조정 이야기가 낮게 오간다.',
        '새 상단이 도착하면서 장터의 자리가 부족해졌다고 한다.',
        '상인 길드가 다음 계약을 두고 조용히 사람을 만나고 있다.',
        '세금 장부를 두고 관리와 상인들이 오래 이야기를 나눴다.',
        '멀리서 온 손님들이 철물 값을 유심히 묻고 다닌다.',
        '곡물 자루를 세는 손길이 평소보다 조금 빨라졌다.',
        '가게마다 외지 손님의 말투를 두고 작은 추측이 오간다.',
        '시장 한쪽에서는 길목 통행료 이야기가 다시 나온다.',
        '오늘 들어온 물건 중 몇 상자는 주인이 바로 드러나지 않았다.',
        '상인들은 날씨보다 길 위의 소문을 먼저 묻고 있다.',
        '낡은 계약서 하나가 다시 장터 사람들 입에 올랐다.',
        '시장 입구에서 새 가격표를 두고 낮은 말다툼이 있었다.',
        '떠돌이 장사꾼이 오래 묵은 물건을 싼값에 내놓았다.',
        '관리 한 명이 장부를 품에 안고 장터를 천천히 돌았다.',
        '상인들은 강가 쪽 길이 전보다 붐빈다고 말한다.',
        '새벽에 들어온 짐마차가 바로 창고로 들어갔다.',
        '거래가 늘었지만 사람들 표정은 꼭 밝지만은 않다.',
        '물건을 사려는 사람보다 소식을 묻는 사람이 더 많았다.',
    ),
    'clinic': (
        '북쪽 길에서 다친 여행자가 도착했다.',
        '약초가 부족하다는 이야기가 나온다.',
        '치료소에는 낯선 손님이 머물고 있다.',
        '피난민들이 젖은 망토를 말리며 길 이야기를 남겼다.',
        '약초상이 산길 쪽 잎이 올해 유난히 말랐다고 했다.',
        '치료소 문턱에는 오래 걷다 온 발자국이 이어져 있다.',
        '회복 중인 손님 하나가 밤새 같은 이름을 중얼거렸다.',
        '북쪽 길을 지난 이들이 작은 상처를 숨기지 못했다.',
        '따뜻한 물을 기다리는 줄이 평소보다 길어졌다.',
        '의사는 길 위의 먼지를 보고도 어느 쪽에서 왔는지 짐작한다.',
        '약재 꾸러미가 늦어져 사람들이 조용히 걱정하고 있다.',
        '치료소 뒤뜰에는 낯선 말발굽 자국이 남아 있다.',
        '여행자들은 쉬면서도 문밖 소리에 자주 고개를 든다.',
        '한 아이가 피난민들의 이야기를 몰래 듣고 있었다.',
        '상처보다 긴장이 더 오래 남는다는 말이 치료소에서 돈다.',
        '약초 냄새 사이로 멀리서 온 소식이 천천히 섞인다.',
        '회복 중인 손님들은 떠난 길보다 돌아갈 길을 더 걱정한다.',
        '치료소 앞 의자는 하루 종일 비지 않았다.',
        '길손 하나가 북쪽 숲 이야기를 꺼내다 말을 흐렸다.',
        '약재를 나누는 손길이 전보다 신중해졌다.',
    ),
    'tavern': (
        '사람들은 아직 확신할 만한 새 이야기를 꺼내지 않는다.',
        '술집 구석에서는 낮에 들은 이야기가 밤이 되며 조금씩 달라진다.',
        '여관주인은 손님들 말을 다 듣고도 모르는 척 잔만 닦는다.',
        '대장장이와 농부 이야기는 누가 먼저 꺼내도 금세 번진다.',
        '누군가는 광장보다 술집에서 진짜 표정이 드러난다고 말한다.',
        '외지 손님 하나가 숲길 이야기를 듣고 말없이 술잔을 내려놓았다.',
        '낡은 탁자마다 오늘의 작은 다툼이 조금씩 다른 말로 남았다.',
        '술집 문이 열릴 때마다 사람들은 먼저 소식부터 묻는다.',
        '여관주인이 늦은 밤 손님의 이름을 따로 기억해 두었다고 한다.',
        '저녁이 깊어질수록 확실한 일보다 그럴듯한 말이 많아진다.',
        '광장에서 끝난 줄 알았던 이야기가 술집에서 다시 살아난다.',
        '손님들은 큰 사건보다 누가 누구를 피했는지에 더 귀를 기울인다.',
        '잔이 오가는 사이에 작은 소문이 하루치 길을 걷는다.',
        '누군가는 에단이 오늘도 주변을 살피고 있었다고 말했다.',
        '술집 뒤쪽 자리에는 늘 먼저 떠나는 사람이 하나 있다.',
        '농부들의 낮은 한숨이 저녁 술집에서 조금 더 크게 들린다.',
        '낯선 방문객이 묻는 질문 때문에 사람들이 잠시 조용해졌다.',
        '문밖에서 들은 말과 술집 안에서 들은 말이 조금 달랐다.',
        '술집 안쪽 자리에서는 하루 전 말다툼이 아직 끝나지 않은 듯 이어진다.',
        '낯선 손님이 남긴 한마디를 두고 사람들 해석이 갈린다.',
    ),
    'back_alley': (
        '어젯밤 창고 근처에서 누군가를 봤다는 이야기가 있다.',
        '요즘 들어 밤마다 마을 밖으로 나가는 사람이 있다고 한다.',
        '상인들이 물건을 숨기고 있다는 소문이 돈다.',
        '발자국 하나가 술집 뒤편에서 끊겼다는 말이 돈다.',
        '골목 안쪽에서는 누가 먼저 소문을 흘렸는지 더 중요하게 여긴다.',
        '낮에는 웃던 사람이 밤에는 다른 이름으로 불렸다고 한다.',
        '닫힌 창문 너머로 작은 금속 소리가 들렸다는 말이 있다.',
        '창고 열쇠를 본 사람이 아무도 없다는 점이 오히려 수상하다고 한다.',
        '누군가 싸움을 말리기보다 키웠다는 뒷말이 남았다.',
        '골목 끝에서는 밝은 곳에서 하지 못한 질문이 오간다.',
        '밤길을 아는 사람들은 발소리만 듣고도 낯선 이를 알아챈다.',
        '사라진 짐보다 그것을 찾지 않는 사람이 더 수상하다는 말이 있다.',
        '어두운 벽 밑에 남은 흙먼지가 평소와 달랐다.',
        '어떤 손님은 술집 문으로 들어와 뒷문으로 나갔다고 한다.',
        '골목 사람들은 오늘도 모르는 척 같은 방향을 본다.',
        '낯선 속삭임이 새벽까지 벽을 타고 남아 있었다.',
        '누군가 기다리던 사람이 오지 않아 골목이 한동안 조용했다.',
        '그림자 속에서는 작은 사건도 오래된 빚처럼 이야기된다.',
        '발자국은 많았지만 같은 방향으로 돌아온 사람은 적었다고 한다.',
        '누군가 창문 아래에 서 있다가 종소리 전에 사라졌다는 말이 있다.',
    ),
}

TUTORIAL_STAGE_UI = {
    'talk_ethan': {
        'title': '튜토리얼 1',
        'subtitle': '회색언덕에 눈을 뜨다',
        'lines': (
            '에단이 너를 구해 이 마을로 데려왔다.',
            '먼저 에단과 대화해 무슨 일이 있었는지 들어보자.',
        ),
    },
    'visit_tavern': {
        'title': '튜토리얼 2',
        'subtitle': '소문이 모이는 곳',
        'lines': (
            '에단의 말대로 술집에서 사람들 입에 오르는 이야기를 살펴보자.',
            '세계는 직접 본 장면보다 먼저 소문으로 다가온다.',
        ),
    },
    'visit_archive': {
        'title': '튜토리얼 3',
        'subtitle': '기록을 읽는 법',
        'lines': (
            '이제 광장으로 돌아가 기록관을 방문해 보자.',
            '기록관으로 이동해야 기록을 살펴볼 수 있다.',
            '소문과 사건은 기록으로 이어질 때 비로소 흐름이 된다.',
        ),
    },
    'wait_in_square': {
        'title': '튜토리얼 4',
        'subtitle': '하루를 흘려보내기',
        'lines': (
            '광장에서 잠시 기다리며 마을 시간이 어떻게 흐르는지 지켜보자.',
            '이 엔진의 핵심은 시간을 흘리고, 흔적을 읽는 일이다.',
        ),
    },
    'complete': {
        'title': '튜토리얼 완료',
        'subtitle': '이제 네 차례다',
        'lines': (
            '이제 회색언덕의 하루를 스스로 이어갈 수 있다.',
            '소문을 모으고, 사건을 보고, 기록을 남겨라.',
        ),
    },
}
TUTORIAL_STAGE_SEQUENCE = ('talk_ethan', 'visit_tavern', 'visit_archive', 'wait_in_square', 'complete')
TUTORIAL_ETHAN_TAVERN_GUIDE = (
    '네가 깨어난 일은 광장 사람들이 봤지만, 진짜 이야기는 술집에서 먼저 돈다. '
    '거기서 사람들 입에 오르는 말을 들어봐.'
)

FACILITY_CONTROL_VISIBILITY = {
    'square': {'wait': True, 'travel': False, 'move': True, 'talk': True, 'choice': True},
    'tavern': {'wait': True, 'travel': False, 'move': True, 'talk': True, 'choice': False},
    'back_alley': {'wait': True, 'travel': False, 'move': True, 'talk': False, 'choice': False},
    'clinic': {'wait': False, 'travel': False, 'move': True, 'talk': True, 'choice': False},
    'market': {'wait': False, 'travel': False, 'move': True, 'talk': True, 'choice': False},
    'archive': {'wait': False, 'travel': False, 'move': False, 'talk': False, 'choice': False},
    'base': {'wait': True, 'travel': False, 'move': False, 'talk': False, 'choice': False},
    'outside': {'wait': False, 'travel': True, 'move': False, 'talk': False, 'choice': False},
}


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
    html {
      height: 100%;
    }
    body {
      margin: 0;
      background: linear-gradient(180deg, #0f1113 0%, #15181b 100%);
      color: var(--text);
      font: 15px/1.5 Georgia, "Times New Roman", serif;
      height: 100svh;
      overflow: hidden;
    }
    .app {
      width: min(100%, 1180px);
      margin: 0 auto;
      height: 100svh;
      padding: max(12px, env(safe-area-inset-top)) max(12px, env(safe-area-inset-right)) max(84px, env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left));
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      gap: clamp(10px, 1.6vmin, 16px);
      overflow: hidden;
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
      grid-template-columns: minmax(0, 1fr);
      gap: clamp(10px, 1.6vmin, 16px);
      align-items: stretch;
      min-height: 0;
      overflow: hidden;
    }
    .main-panel {
      display: grid;
      gap: 14px;
      min-height: 0;
      overflow-y: auto;
      overscroll-behavior: contain;
      padding-bottom: max(96px, env(safe-area-inset-bottom));
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
    .system-toggle {
      position: fixed;
      right: 0;
      top: 50%;
      z-index: 18;
      min-height: 86px;
      padding: 10px 8px;
      border-right: 0;
      transform: translateY(-50%);
      writing-mode: vertical-rl;
      text-orientation: mixed;
      background: #252a30;
      box-shadow: 0 8px 28px rgba(0, 0, 0, 0.45);
    }
    .system-drawer {
      position: fixed;
      top: max(10px, env(safe-area-inset-top));
      right: max(10px, env(safe-area-inset-right));
      bottom: max(10px, env(safe-area-inset-bottom));
      z-index: 19;
      width: min(420px, calc(100vw - 20px));
      overflow-y: auto;
      overscroll-behavior: contain;
    }
    .system-drawer-header {
      position: sticky;
      top: 0;
      z-index: 1;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      margin: -16px -16px 12px;
      padding: 12px 16px;
    }
    .system-drawer-header h2 {
      margin: 0;
    }
    .button-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .button-row.tight button {
      min-height: 44px;
    }
    button {
      background: var(--panel-2);
      color: var(--text);
      border: 1px solid var(--line);
      padding: 8px 12px;
      cursor: pointer;
      font: inherit;
      min-height: 44px;
    }
    button:hover { border-color: var(--accent); }
    button.secondary { color: var(--muted); }
    button.active {
      border-color: var(--accent);
      color: var(--accent);
    }
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
    .facility-view {
      background: var(--panel-2);
      border: 1px solid var(--line);
      padding: 14px;
      display: grid;
      gap: 12px;
    }
    #facilitySummary {
      list-style: none;
      padding-left: 0;
      margin: 0;
      display: grid;
      gap: 6px;
    }
    #facilitySummary li {
      margin: 0;
      line-height: 1.4;
    }
    .story-stack {
      display: grid;
      gap: 10px;
    }
    .card-list {
      display: grid;
      gap: 10px;
    }
    .mini-card {
      background: rgba(0, 0, 0, 0.18);
      border: 1px solid var(--line);
      padding: 12px;
    }
    .mini-card h3 {
      margin: 0 0 8px;
      color: var(--text);
      font-size: 15px;
    }
    .mini-card p {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }
    .mini-card ul {
      margin-top: 8px;
      color: var(--text);
    }
    .error {
      color: var(--danger);
      font-size: 13px;
      min-height: 18px;
    }
    .guidance-backdrop {
      position: fixed;
      inset: 0;
      z-index: 20;
      display: grid;
      place-items: center;
      padding: 20px;
      background: rgba(0, 0, 0, 0.62);
    }
    .guidance-dialog {
      width: min(420px, 100%);
      background: #1b1e23;
      border: 1px solid var(--accent);
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.55);
      padding: 18px;
    }
    .guidance-dialog h2 {
      margin-bottom: 12px;
    }
    .guidance-dialog p {
      margin: 0 0 16px;
      line-height: 1.55;
    }
    [hidden] { display: none !important; }
    .surface-detail {
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }
    .surface-detail summary {
      font-size: 15px;
    }
    @media (orientation: landscape) and (max-height: 720px) {
      body {
        font-size: 14px;
      }
      .summary strong {
        font-size: 18px;
      }
      .panel {
        padding: 12px;
      }
      .facility-view,
      .mini-card {
        padding: 10px;
      }
      h1 { font-size: 19px; }
      h2 { font-size: 16px; }
    }
    @media (orientation: portrait) {
      .app {
        width: min(100%, 540px);
      }
      .system-toggle {
        top: auto;
        right: max(0px, env(safe-area-inset-right));
        bottom: calc(84px + env(safe-area-inset-bottom));
        transform: none;
      }
    }
    @media (max-width: 820px) {
      .app {
        padding: 12px;
      }
      .grid { grid-template-columns: 1fr; }
      .summary {
        display: grid;
        gap: 6px;
      }
      .button-row {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .button-row button {
        width: 100%;
      }
      h1 { font-size: 19px; }
      h2 { font-size: 16px; }
      .panel {
        padding: 14px;
      }
      .facility-view {
        padding: 12px;
      }
    }
    @media (max-width: 480px) and (orientation: portrait) {
      body {
        font-size: 14px;
      }
      .app {
        padding: 10px;
      }
      .summary strong {
        font-size: 18px;
      }
      .button-row {
        gap: 8px;
      }
      button {
        min-height: 46px;
        padding: 8px 10px;
      }
      .mini-card {
        padding: 10px;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <div class="panel">
      <h1>Village RP Engine MVP UI</h1>
      <div class="summary">
        <div><strong id="dayTick">오늘 아침</strong></div>
        <div>현재 정착지: <span id="activeSettlement">회색언덕 마을</span></div>
        <div>현재 위치: <span id="playerLocation">광장</span></div>
        <div>Mode: <span>RP</span></div>
      </div>
      <div class="section">
        <h2>최근 저장 목록</h2>
        <ul id="recentSaves"></ul>
      </div>
    </div>

    <div class="grid">
      <div class="panel main-panel">
        <div class="story-stack" id="overviewCards"></div>
        <div class="facility-view">
          <div>
            <h2 id="facilityTitle">광장</h2>
            <div class="hint" id="facilityDescription"></div>
          </div>
          <ul id="facilitySummary"></ul>
          <div class="button-row tight" id="facilityActionButtons"></div>
          <div class="card-list" id="facilityCards"></div>
          <div class="card-list" id="facilityNpcCards"></div>
        </div>
        <div class="section">
          <h2>시설</h2>
          <div class="button-row tight" id="facilityButtons"></div>
          <ul class="hint" id="facilityHints"></ul>
        </div>
      </div>

      <div class="controls system-drawer" id="systemDrawer" hidden>
        <div class="system-drawer-header">
          <h2>시스템 보기</h2>
          <button class="secondary" id="systemCloseButton" type="button">닫기</button>
        </div>
        <div class="panel" id="actionPanel" hidden>
          <h2>행동</h2>
          <div class="section" id="waitSection">
            <h3>대기</h3>
            <div class="button-row">
              <button data-action="wait">대기</button>
              <button class="secondary" id="saveButton">저장</button>
              <button class="secondary" id="loadButton">불러오기</button>
              <button class="secondary" id="resetButton">리셋</button>
            </div>
          </div>
          <div class="section" id="travelSection">
            <h3>정착지 이동</h3>
            <div class="button-row" id="travelButtons"></div>
          </div>
          <div class="section" id="moveSection">
            <h3>위치 이동</h3>
            <div class="button-row" id="moveButtons"></div>
          </div>
          <div class="section" id="talkSection">
            <h3>대화 가능 인물</h3>
            <div class="button-row" id="talkButtons"></div>
            <div class="npc-list" id="presentNpcs"></div>
          </div>
          <div class="section" id="choiceSection">
            <h3>선택</h3>
            <div class="button-row" id="choiceButtons"></div>
            <div class="npc-list" id="specialNpcState"></div>
          </div>
          <div class="error" id="errorText"></div>
          <div class="hint">ACTIVE settlement만 장면과 대화를 렌더링하고, 다른 settlement는 경량 업데이트만 수행한다.</div>
        </div>

        <div class="panel">
          <details open>
            <summary>장면과 대화</summary>
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
          </details>
        </div>

        <div class="panel">
          <details open>
            <summary>소문과 기록</summary>
            <div class="section">
              <h2>Rumor 요약</h2>
              <ul id="rumors"></ul>
            </div>
            <div class="section">
              <h2>Chronicle 핵심</h2>
              <ul id="chronicleHighlights"></ul>
            </div>
          </details>
        </div>

        <div class="panel">
          <details>
            <summary>관계와 퀘스트</summary>
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
          </details>
        </div>

        <div class="panel">
          <details>
            <summary>개발자 로그: World Log</summary>
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

  <button class="system-toggle" id="systemToggleButton" type="button">시스템</button>

  <div class="guidance-backdrop" id="guidancePopup" hidden role="dialog" aria-modal="true" aria-labelledby="guidanceTitle">
    <div class="guidance-dialog">
      <h2 id="guidanceTitle">안내</h2>
      <p id="guidanceMessage"></p>
      <div class="button-row">
        <button id="guidanceCloseButton" type="button">확인</button>
      </div>
    </div>
  </div>

  <script>
    const overviewCards = document.getElementById('overviewCards');
    const facilityButtons = document.getElementById('facilityButtons');
    const facilityHints = document.getElementById('facilityHints');
    const facilityTitle = document.getElementById('facilityTitle');
    const facilityDescription = document.getElementById('facilityDescription');
    const facilitySummary = document.getElementById('facilitySummary');
    const facilityActionButtons = document.getElementById('facilityActionButtons');
    const facilityCards = document.getElementById('facilityCards');
    const facilityNpcCards = document.getElementById('facilityNpcCards');
    const moveButtons = document.getElementById('moveButtons');
    const travelButtons = document.getElementById('travelButtons');
    const talkButtons = document.getElementById('talkButtons');
    const choiceButtons = document.getElementById('choiceButtons');
    const presentNpcs = document.getElementById('presentNpcs');
    const specialNpcState = document.getElementById('specialNpcState');
    const errorText = document.getElementById('errorText');
    const waitSection = document.getElementById('waitSection');
    const travelSection = document.getElementById('travelSection');
    const moveSection = document.getElementById('moveSection');
    const talkSection = document.getElementById('talkSection');
    const choiceSection = document.getElementById('choiceSection');
    const guidancePopup = document.getElementById('guidancePopup');
    const guidanceMessage = document.getElementById('guidanceMessage');
    const guidanceCloseButton = document.getElementById('guidanceCloseButton');
    const systemDrawer = document.getElementById('systemDrawer');
    const systemToggleButton = document.getElementById('systemToggleButton');
    const systemCloseButton = document.getElementById('systemCloseButton');

    function showGuidancePopup(message) {
      const text = message || '요청 처리 중 오류가 발생했다.';
      errorText.textContent = text;
      guidanceMessage.textContent = text;
      guidancePopup.hidden = false;
      guidanceCloseButton.focus();
    }

    function hideGuidancePopup() {
      guidancePopup.hidden = true;
    }

    guidanceCloseButton.onclick = hideGuidancePopup;
    guidancePopup.onclick = (event) => {
      if (event.target === guidancePopup) {
        hideGuidancePopup();
      }
    };

    function openSystemDrawer() {
      systemDrawer.hidden = false;
      systemCloseButton.focus();
    }

    function closeSystemDrawer() {
      systemDrawer.hidden = true;
      systemToggleButton.focus();
    }

    systemToggleButton.onclick = openSystemDrawer;
    systemCloseButton.onclick = closeSystemDrawer;

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

    function handlePayload(payload) {
      if (payload.client_action === 'save') {
        document.getElementById('saveButton').click();
        return;
      }
      if (payload.client_action === 'load') {
        document.getElementById('loadButton').click();
        return;
      }
      if (payload.client_action === 'reset') {
        document.getElementById('resetButton').click();
        return;
      }
      performAction(payload);
    }

    function renderCards(target, cards) {
      target.innerHTML = '';
      for (const card of cards || []) {
        const item = document.createElement('div');
        item.className = 'mini-card';
        const title = document.createElement('h3');
        title.textContent = card.title;
        const subtitle = document.createElement('p');
        subtitle.textContent = card.subtitle || '';
        item.appendChild(title);
        item.appendChild(subtitle);
        if (card.lines && card.lines.length) {
          const list = document.createElement('ul');
          for (const lineText of card.lines) {
            const li = document.createElement('li');
            li.textContent = lineText;
            list.appendChild(li);
          }
          item.appendChild(list);
        }
        if (card.actions && card.actions.length) {
          const row = document.createElement('div');
          row.className = 'button-row';
          for (const action of card.actions) {
            const button = document.createElement('button');
            button.textContent = action.label;
            if (action.secondary) {
              button.classList.add('secondary');
            }
            button.onclick = () => handlePayload(action.payload);
            row.appendChild(button);
          }
          item.appendChild(row);
        }
        target.appendChild(item);
      }
    }

    function renderState(data) {
      document.getElementById('dayTick').textContent = data.display_time || data.time_phase;
      document.getElementById('activeSettlement').textContent = data.active_settlement_name || data.active_settlement_id;
      document.getElementById('playerLocation').textContent = data.player_location;
      renderCards(overviewCards, data.overview_cards);
      renderList('scenes', data.visible_scenes);
      renderList('dialogues', data.dialogues, (item) => `${item.speaker_name}: "${item.text}"`);
      renderList('events', data.triggered_events, (item) => item.outcome_text);
      renderList('rumors', data.rumor_lines);
      renderList('chronicleHighlights', data.chronicle_highlights);
      renderList('quests', data.quests);
      renderList('playerRelationships', data.player_relationships);
      renderList('relationships', data.relationships);
      renderList('recentSaves', data.recent_saves, (item) => `슬롯 ${item.slot} | ${item.display_time} | ${item.active_settlement_name} | ${item.saved_at}`);

      facilityButtons.innerHTML = '';
      for (const facility of data.facilities) {
        const button = document.createElement('button');
        button.textContent = facility.display_label || facility.label;
        if (facility.facility_id === data.selected_facility_id) {
          button.classList.add('active');
        }
        button.disabled = facility.disabled === true;
        button.title = facility.access_hint || '';
        button.onclick = () => handlePayload(facility.action_payload || { action_type: 'select_facility', facility_id: facility.facility_id });
        facilityButtons.appendChild(button);
      }
      renderList('facilityHints', data.facility_hints);
      facilityTitle.textContent = data.facility_view.title;
      facilityDescription.textContent = data.facility_view.description;
      renderList('facilitySummary', data.facility_view.summary_lines);
      facilityActionButtons.innerHTML = '';
      for (const action of data.facility_view.actions) {
        const button = document.createElement('button');
        button.textContent = action.label;
        if (action.secondary) {
          button.classList.add('secondary');
        }
        button.onclick = () => handlePayload(action.payload);
        facilityActionButtons.appendChild(button);
      }
      renderCards(facilityCards, data.facility_view.cards);
      facilityNpcCards.innerHTML = '';
      for (const npc of data.facility_view.npc_cards) {
        const item = document.createElement('div');
        item.className = 'mini-card';
        const title = document.createElement('h3');
        title.textContent = `${npc.name} | ${npc.role}`;
        const subtitle = document.createElement('p');
        subtitle.textContent = `성격: ${npc.personality} | 관심사: ${npc.current_interest}`;
        item.appendChild(title);
        item.appendChild(subtitle);
        if (npc.lines && npc.lines.length) {
          const list = document.createElement('ul');
          for (const lineText of npc.lines) {
            const li = document.createElement('li');
            li.textContent = lineText;
            list.appendChild(li);
          }
          item.appendChild(list);
        }
        const row = document.createElement('div');
        row.className = 'button-row';
        const talkButton = document.createElement('button');
        talkButton.textContent = '대화하기';
        talkButton.onclick = () => performAction({ action_type: 'talk', target_npc_id: npc.npc_id });
        row.appendChild(talkButton);
        item.appendChild(row);
        facilityNpcCards.appendChild(item);
      }

      document.getElementById('worldLog').textContent = data.world_log.join('\n');
      document.getElementById('rumorLog').textContent = data.rumor_lines.join('\n') || '없음';
      document.getElementById('npcStateLog').textContent = data.npc_status_lines.join('\n');
      document.getElementById('chronicleLog').textContent = data.chronicle_lines.join('\n');
      waitSection.hidden = !data.ui_sections.wait;
      travelSection.hidden = !data.ui_sections.travel;
      moveSection.hidden = !data.ui_sections.move;
      talkSection.hidden = !data.ui_sections.talk;
      choiceSection.hidden = !data.ui_sections.choice;

      travelButtons.innerHTML = '';
      for (const option of (data.available_settlement_options || data.available_settlements.map((id) => ({ settlement_id: id, label: id })))) {
        const button = document.createElement('button');
        button.textContent = option.label;
        button.onclick = () => performAction({ action_type: 'travel', target_settlement_id: option.settlement_id, travel_mode: 'walk' });
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
        showGuidancePopup(data.error || '요청 처리 중 오류가 발생했다.');
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
        showGuidancePopup(data.error || '저장 중 오류가 발생했다.');
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
        showGuidancePopup(data.error || '불러오기 중 오류가 발생했다.');
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


def _normalize_facility_id(snapshot: WorldSnapshot, facility_id: str | None) -> str:
    available_ids = [facility.facility_id for facility in snapshot.settlement_definition.facilities if facility.enabled]
    if facility_id in available_ids:
        return facility_id
    return available_ids[0] if available_ids else DEFAULT_FACILITY_ID


def _get_facility_definition(snapshot: WorldSnapshot, facility_id: str) -> Any | None:
    for facility in snapshot.settlement_definition.facilities:
        if facility.facility_id == facility_id:
            return facility
    return None


def _can_access_facility_from_current_location(snapshot: WorldSnapshot, facility_id: str) -> bool:
    facility = _get_facility_definition(snapshot, facility_id)
    if facility is None or not facility.enabled:
        return False

    current_location = snapshot.settlement_state.player_location or ''
    if facility.target_location is not None:
        return current_location == facility.target_location

    return current_location == '광장'


def _facility_access_hint(snapshot: WorldSnapshot, facility_id: str) -> str:
    facility = _get_facility_definition(snapshot, facility_id)
    if facility is None or _can_access_facility_from_current_location(snapshot, facility_id):
        return ''
    if facility.facility_id == 'square':
        return '다른 시설을 보려면 광장으로 돌아가야 한다.'
    if facility.facility_id == 'archive':
        return '기록관으로 이동해야 기록을 살펴볼 수 있다.'
    if facility.facility_id == 'back_alley':
        return '뒷골목으로 이동해야 조사할 수 있다.'
    if facility.facility_id == 'market':
        return '시장은 마을 광장에서 이동한 뒤 이용할 수 있다.'
    if facility.facility_id == 'outside':
        return '도시 밖으로 나가려면 먼저 광장으로 돌아가야 한다.'
    if facility.target_location is not None:
        return f'{facility.label}(으)로 이동해야 이용할 수 있다.'
    return f'{facility.label}(으)로 이동해야 이용할 수 있다.'


def _resolve_default_facility_for_current_location(snapshot: WorldSnapshot) -> str:
    current_location = snapshot.settlement_state.player_location or ''
    for facility in snapshot.settlement_definition.facilities:
        if facility.enabled and facility.target_location == current_location:
            return facility.facility_id
    return DEFAULT_FACILITY_ID


def _normalize_selected_facility(snapshot: WorldSnapshot, facility_id: str | None) -> str:
    normalized = _normalize_facility_id(snapshot, facility_id)
    if _can_access_facility_from_current_location(snapshot, normalized):
        return normalized
    return _resolve_default_facility_for_current_location(snapshot)


def _stress_label(stress: int) -> str:
    if stress <= 25:
        return '평온'
    if stress <= 50:
        return '긴장'
    if stress <= 75:
        return '불안정'
    if stress <= 100:
        return '위험'
    return '위기'


def _security_label(security: int) -> str:
    if security >= 75:
        return '견고함'
    if security >= 55:
        return '안정'
    if security >= 35:
        return '흔들림'
    return '취약'


def format_settlement_name(snapshot: WorldSnapshot, settlement_id: str, *, short: bool = False) -> str:
    overrides = SETTLEMENT_SHORT_NAME_OVERRIDES if short else SETTLEMENT_DISPLAY_NAME_OVERRIDES
    if settlement_id in overrides:
        return overrides[settlement_id]
    definition = snapshot.settlement_definitions.get(settlement_id)
    if definition is not None and definition.flavor.title:
        return definition.flavor.title
    return settlement_id


def _format_phase_for_tick(tick: int) -> str:
    return TIME_PHASES[tick % len(TIME_PHASES)]


def format_time_for_player(snapshot: WorldSnapshot, day: int, tick: int) -> str:
    phase = _format_phase_for_tick(tick)
    return _format_day_phase_for_player(snapshot, day, phase)


def _format_day_phase_for_player(snapshot: WorldSnapshot, day: int, phase: str) -> str:
    current_day = snapshot.settlement_state.day
    delta = max(current_day - day, 0)
    if delta == 0:
        return f'오늘 {phase}'
    if delta == 1:
        if phase == '밤':
            return '어젯밤'
        return f'어제 {phase}'
    if delta == 2:
        return f'이틀 전 {phase}'
    if delta <= 4:
        return f'{delta}일 전 {phase}'
    return '며칠 전'


def _localize_time_tokens(snapshot: WorldSnapshot, text: str) -> str:
    def replace_tick(match: re.Match[str]) -> str:
        return f"{format_time_for_player(snapshot, int(match.group(1)), int(match.group(2)))} |"

    def replace_phase(match: re.Match[str]) -> str:
        return f"{_format_day_phase_for_player(snapshot, int(match.group(1)), match.group(2))} |"

    localized = re.sub(r'^Day\s+(\d+)\s+Tick\s+(\d+)\s*\|', replace_tick, text)
    localized = re.sub(r'^Day\s+(\d+)\s+([가-힣]+)\s*\|', replace_phase, localized)
    return localized


def _localize_settlement_ids(snapshot: WorldSnapshot, text: str) -> str:
    localized = text
    for settlement_id in sorted(snapshot.settlement_definitions, key=len, reverse=True):
        short_name = format_settlement_name(snapshot, settlement_id, short=True)
        full_name = format_settlement_name(snapshot, settlement_id)
        for location in ('술집', '광장', '시장', '창고', '뒷골목', '대장간', '치료소'):
            localized = localized.replace(f'{settlement_id}에서 {location}에서', f'{short_name} {location}에서')
            localized = localized.replace(f'{settlement_id}의 {location}에서', f'{short_name} {location}에서')
            localized = localized.replace(f'{settlement_id} {location}에서', f'{short_name} {location}에서')
        localized = localized.replace(f'{settlement_id}에서', f'{short_name}에서')
        localized = localized.replace(f'{settlement_id}의', f'{short_name}의')
        localized = re.sub(rf'\b{re.escape(settlement_id)}\b', full_name, localized)
    return localized


def format_player_surface_text(snapshot: WorldSnapshot, text: str) -> str:
    return _localize_time_tokens(snapshot, _localize_settlement_ids(snapshot, _strip_system_prefix(text).strip()))


def _player_surface_text_or_none(snapshot: WorldSnapshot, text: str) -> str | None:
    localized = format_player_surface_text(snapshot, text)
    if not localized or _is_raw_state_entry_text(localized):
        return None
    return localized


def _format_dialogue_text_for_player(snapshot: WorldSnapshot, speaker_id: str, text: str) -> str | None:
    if speaker_id == 'village_elder' and _quest_status(snapshot) == 'refused' and _quest_penalty_ticks(snapshot) > 0:
        return '촌장은 아직 당신을 마을 사람으로 받아들이기엔 이르다고 판단한 듯하다.'
    if speaker_id == 'ethan' and snapshot.interaction_runtime_state.tutorial_stage == 'visit_tavern':
        return TUTORIAL_ETHAN_TAVERN_GUIDE
    return _player_surface_text_or_none(snapshot, text)


def _status_summary_lines(snapshot: WorldSnapshot) -> list[str]:
    state = snapshot.settlement_state
    return [
        f'치안: {_security_label(state.security)}',
        f'분위기: {_stress_label(state.stress)}',
        _stress_context_sentence(state.stress),
    ]


def _is_raw_state_entry_text(text: str) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in RAW_PLAYER_SURFACE_MARKERS)


def is_raw_state_entry(entry: Any) -> bool:
    text = getattr(entry, 'text', str(entry))
    return _is_raw_state_entry_text(text)


def _stress_context_sentence(stress: int) -> str:
    label = _stress_label(stress)
    if label == '평온':
        return '마을은 겉보기엔 차분하지만, 사람들은 작은 소문에도 귀를 기울인다.'
    if label == '긴장':
        return '아직 큰 사건은 없지만 사람들의 말수가 조금 줄었다.'
    if label == '불안정':
        return '술집과 광장 사이에서 같은 소문이 빠르게 되풀이되고 있다.'
    return '길 위의 불안이 마을 안쪽까지 번지고 있다.'


def format_settlement_mood(snapshot: WorldSnapshot) -> list[str]:
    state = snapshot.settlement_state
    return [
        f'치안: {_security_label(state.security)}',
        f'분위기: {_stress_label(state.stress)}',
        _stress_context_sentence(state.stress),
    ]


def format_player_facing_line(entry: Any, snapshot: WorldSnapshot | None = None) -> str | None:
    text = _strip_system_prefix(getattr(entry, 'text', str(entry)))
    if snapshot is not None:
        text = format_player_surface_text(snapshot, text)
    if not text or _is_raw_state_entry_text(text):
        return None
    day = getattr(entry, 'day', None)
    tick = getattr(entry, 'tick', None)
    if day is not None and tick is not None:
        if snapshot is not None:
            return f'{format_time_for_player(snapshot, day, tick)} | {text}'
        return text
    return text


def filter_player_facing_entries(entries: Any, snapshot: WorldSnapshot | None = None) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        line = format_player_facing_line(entry, snapshot)
        if line is not None:
            _append_unique_line(lines, line)
    return lines


def _strip_system_prefix(text: str) -> str:
    for prefix in ('이벤트 발생:', '상태 부여:', '퀘스트 시작:', '퀘스트 완료:'):
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text.strip()


class TavernRumorFormatter:
    def __init__(self, snapshot: WorldSnapshot) -> None:
        self.snapshot = snapshot
        self.prefix = snapshot.settlement_definition.flavor.rumor_intro

    def format_entry(self, entry: Any) -> str | None:
        text = format_player_surface_text(self.snapshot, entry.text)
        if not text or _is_raw_state_entry_text(text):
            if entry.category == 'STATE_CHANGE':
                return f'요즘 마을 분위기가 {_stress_label(self.snapshot.settlement_state.stress)} 쪽으로 기울고 있다는 말이 돈다.'
            return None
        if entry.category == 'EVENT':
            return self._event_to_rumor(text)
        if entry.category in {'RUMOR', 'STATE_CHANGE'}:
            return self._with_prefix(text)
        return None

    def _event_to_rumor(self, text: str) -> str:
        if '말다툼' in text or '언성' in text:
            return '대장장이와 농부가 또 언성을 높였다더군.'
        if '상인' in text:
            return '상인들이 남긴 이야기가 사람들 입에 오르내린다.'
        if '여관주인' in text or '정리' in text:
            return '술집 주인이 밤늦게까지 자리를 정리했다는 말이 돈다.'
        return self._with_prefix(f'{text}는 이야기가 돈다.')

    def _with_prefix(self, text: str) -> str:
        if self.prefix and not text.startswith(self.prefix):
            return f'{self.prefix} {text}'
        return text


class BackAlleyRumorFormatter:
    def __init__(self, snapshot: WorldSnapshot) -> None:
        self.snapshot = snapshot

    def format_entry(self, entry: Any) -> str | None:
        text = format_player_surface_text(self.snapshot, entry.text)
        if not text or _is_raw_state_entry_text(text):
            return self._mood_rumor() if entry.category == 'STATE_CHANGE' else None
        if entry.category == 'EVENT':
            return self._event_to_hidden_rumor(text)
        if entry.category == 'RUMOR':
            return self._rumor_to_hidden_rumor(text)
        return None

    def _event_to_hidden_rumor(self, text: str) -> str:
        if '말다툼' in text or '언성' in text:
            return '누군가 일부러 그 싸움을 키웠다는 말이 골목 안쪽에서 돈다.'
        if '상인' in text or '시장' in text:
            return '상인들이 감추고 지나간 짐이 있었다는 말이 낮게 오간다.'
        if '여관주인' in text or '술집' in text:
            return '술집 뒤편에서 밤늦게까지 꺼지지 않은 목소리가 있었다고 한다.'
        return '밝은 자리에서는 나오지 않는 뒷말이 골목 끝에 남아 있다.'

    def _rumor_to_hidden_rumor(self, text: str) -> str:
        if '싸움' in text or '언성' in text or '다툼' in text:
            return '그 소란 뒤에 누군가의 부추김이 있었다는 말이 돈다.'
        if '소문' in text:
            return '누가 처음 퍼뜨렸는지 모를 말이 그림자처럼 따라붙는다.'
        return '밤마다 창고 근처를 맴도는 사람이 있다는 소문이 있다.'

    def _mood_rumor(self) -> str:
        label = _stress_label(self.snapshot.settlement_state.stress)
        if label in {'위험', '위기'}:
            return '마을의 불안이 골목 안쪽에서 더 짙게 웅크리고 있다.'
        if label == '불안정':
            return '같은 이야기를 누군가 일부러 되풀이하게 만든다는 말이 있다.'
        return '겉으로 조용한 날에도 골목에는 작은 기척이 남는다.'


def _entry_matches_facility(entry: Any, formatted_text: str, facility_id: str) -> bool:
    keywords = FACILITY_RUMOR_KEYWORDS.get(facility_id)
    if not keywords:
        return True
    source_text = getattr(entry, 'text', '')
    return any(keyword in source_text for keyword in keywords)


def _facility_default_rumors(facility_id: str) -> tuple[str, ...]:
    return FACILITY_DEFAULT_RUMORS.get(facility_id, ())


def _rotated_facility_default_rumors(snapshot: WorldSnapshot, facility_id: str) -> tuple[str, ...]:
    defaults = _facility_default_rumors(facility_id)
    if not defaults:
        return ()
    seed = snapshot.settlement_state.day + snapshot.settlement_state.tick + sum(ord(ch) for ch in snapshot.active_settlement_id + facility_id)
    start = seed % len(defaults)
    return defaults[start:] + defaults[:start]


def _build_rumor_briefing(snapshot: WorldSnapshot, facility_id: str = 'tavern') -> list[str]:
    chronicle_query = build_chronicle_query(snapshot)
    entries = [
        *chronicle_query.query_entries(category='RUMOR', settlement_id=snapshot.active_settlement_id, limit=3).entries,
        *chronicle_query.query_entries(category='EVENT', settlement_id=snapshot.active_settlement_id, limit=2).entries,
        *chronicle_query.query_entries(category='STATE_CHANGE', settlement_id=snapshot.active_settlement_id, limit=2).entries,
    ]
    bias_terms = tuple(
        keyword
        for bias in snapshot.settlement_definition.flavor.rumor_bias
        for keyword in RUMOR_BIAS_KEYWORDS.get(bias, ())
    )
    weighted_entries = sorted(
        entries,
        key=lambda entry: (
            sum(1 for term in bias_terms if term and term in entry.text),
            1 if entry.category == 'RUMOR' else 0,
            entry.day,
            entry.tick,
        ),
        reverse=True,
    )
    formatter = TavernRumorFormatter(snapshot)
    lines: list[str] = []
    seen: set[str] = set()
    if _quest_status(snapshot) == 'refused':
        if facility_id == 'tavern':
            _append_unique_line(lines, '촌장이 부탁까지 했다던데, 일이 잘 풀리진 않은 모양이다.')
        elif facility_id == 'back_alley':
            _append_unique_line(lines, '누군가는 그 싸움을 오히려 반기는 것 같다는 말이 돈다.')
    for entry in weighted_entries:
        text = formatter.format_entry(entry)
        if text and facility_id in {'market', 'clinic'} and not _entry_matches_facility(entry, text, facility_id):
            continue
        if not text or text in seen:
            continue
        seen.add(text)
        lines.append(text)
        if len(lines) >= 3:
            break
    for default_line in _rotated_facility_default_rumors(snapshot, facility_id):
        _append_unique_line(lines, default_line)
        if len(lines) >= 3:
            break
    return lines or ['오늘은 아직 새로 퍼진 이야기가 없다.']


def _build_tavern_info_result_card(snapshot: WorldSnapshot) -> dict[str, Any]:
    lines: list[str] = []
    formatter = TavernRumorFormatter(snapshot)
    primary_narration = _get_primary_narration_line(snapshot)
    if primary_narration is not None:
        _append_unique_line(lines, _player_surface_text_or_none(snapshot, primary_narration))
    for event in snapshot.presentation_state.triggered_event_summaries[:2]:
        event_text = _player_surface_text_or_none(snapshot, event.outcome_text)
        if event_text is not None:
            _append_unique_line(lines, formatter._event_to_rumor(event_text))
    for rumor_line in _build_rumor_briefing(snapshot, 'tavern'):
        _append_unique_line(lines, rumor_line)
    return {
        'title': '정보 수집 결과',
        'subtitle': '술집에서 건져 올린 이야기',
        'lines': lines[:3] or ['사람들은 아직 확신할 만한 새 이야기를 꺼내지 않는다.'],
    }


def _dedupe_card_lines(card: dict[str, Any], shown_texts: set[str], fallback_text: str) -> dict[str, Any]:
    unseen_lines: list[str] = []
    for line in card.get('lines', []):
        if line in shown_texts:
            continue
        shown_texts.add(line)
        _append_unique_line(unseen_lines, line)
    return {
        **card,
        'lines': unseen_lines[:3] or [fallback_text],
    }


def _build_back_alley_rumor_lines(snapshot: WorldSnapshot) -> list[str]:
    chronicle_query = build_chronicle_query(snapshot)
    entries = [
        *chronicle_query.query_entries(category='RUMOR', settlement_id=snapshot.active_settlement_id, limit=2).entries,
        *chronicle_query.query_entries(category='EVENT', settlement_id=snapshot.active_settlement_id, limit=2).entries,
    ]
    formatter = BackAlleyRumorFormatter(snapshot)
    lines: list[str] = []
    if _quest_status(snapshot) == 'refused':
        _append_unique_line(lines, '누군가는 그 싸움을 오히려 반기는 것 같다는 말이 돈다.')
    for entry in entries:
        text = formatter.format_entry(entry)
        if text:
            _append_unique_line(lines, text)
    for line in _rotated_facility_default_rumors(snapshot, 'back_alley'):
        _append_unique_line(lines, line)
        if len(lines) >= 3:
            break
    return lines[:3]


def _build_back_alley_info_result_card(snapshot: WorldSnapshot) -> dict[str, Any]:
    return {
        'title': '살펴본 흔적',
        'subtitle': '공식 기록 밖에서 들리는 말',
        'lines': _build_back_alley_rumor_lines(snapshot),
    }


def _build_travel_arrival_card(snapshot: WorldSnapshot) -> dict[str, Any]:
    flavor_title = format_settlement_name(snapshot, snapshot.active_settlement_id)
    mood_line = _stress_context_sentence(snapshot.settlement_state.stress)
    if snapshot.active_settlement_id == 'village_2':
        arrival_line = '치료소 앞에는 길 위에서 온 사람들의 낮은 이야기가 모여 있다.'
    elif snapshot.active_settlement_id == 'town_1':
        arrival_line = '상인들의 목소리가 분주하게 오가지만, 어딘가 긴장감이 섞여 있다.'
    else:
        arrival_line = '광장에는 낮은 목소리의 소문들이 흩어져 있다.'
    trust_line = ''
    if snapshot.active_settlement_id != 'village_1':
        home_status = _resident_status_for(snapshot, 'village_1')
        if home_status == 'resident':
            trust_line = '수문장은 회색언덕에서 온 사람이라며 당신을 안쪽으로 들여보냈다.'
        elif _has_ethan_guarantee(snapshot):
            trust_line = '에단이 한 걸음 앞으로 나서자, 수문장은 경계를 조금 누그러뜨렸다.'
        else:
            trust_line = '수문장이 당신을 의심스럽게 바라보며 추천장이 있는지 물었다.'
    return {
        'title': f'{flavor_title}에 도착했다',
        'subtitle': '이동 완료',
        'lines': [line for line in (arrival_line, trust_line, mood_line) if line],
    }


def _build_clinic_observation_card(topic: str | None) -> dict[str, Any]:
    if topic == 'patients':
        lines = [
            '긴 여행 끝에 도착한 사람들이 의자마다 몸을 기대고 있다.',
            '누군가는 북쪽 길에서 넘어진 상인을 보았다고 낮게 말한다.',
        ]
    elif topic == 'herbs':
        lines = [
            '마른 약초 꾸러미가 선반 한쪽에 얼마 남지 않았다.',
            '약재를 싣고 오던 길손이 늦어지고 있다는 이야기가 나온다.',
        ]
    else:
        lines = [
            '낯선 여행자가 치료소 구석에서 길 위의 이야기를 조용히 풀어놓는다.',
            '사람들은 다친 이들이 어디서 왔는지보다 어디로 가려는지를 더 궁금해한다.',
        ]
    return {
        'title': '치료소에서 들은 말',
        'subtitle': '회복과 길 위의 소식',
        'lines': lines,
    }


def _format_chronicle_line(entry: Any, snapshot: WorldSnapshot) -> str | None:
    return format_player_facing_line(entry, snapshot)


def _should_hide_square_story_card(snapshot: WorldSnapshot) -> bool:
    return snapshot.interaction_runtime_state.intro_dismissed and snapshot.settlement_state.tick >= 4


def _build_archive_cards(snapshot: WorldSnapshot) -> list[dict[str, Any]]:
    chronicle_query = build_chronicle_query(snapshot)
    archive_intro = snapshot.settlement_definition.flavor.archive_intro
    cards: list[dict[str, Any]] = []
    card_sources = [
        ('사건 기록', chronicle_query.query_entries(category='EVENT', settlement_id=snapshot.active_settlement_id, limit=3).entries),
        ('소문 기록', chronicle_query.query_entries(category='RUMOR', settlement_id=snapshot.active_settlement_id, limit=3).entries),
        ('플레이어 행적', tuple(item.entry for item in get_player_timeline(snapshot, limit=2))),
    ]
    for title, entries in card_sources:
        lines = filter_player_facing_entries(entries, snapshot)
        if not lines:
            continue
        cards.append(
            {
                'title': title,
                'subtitle': archive_intro or f'{len(lines)}개의 기록',
                'lines': lines,
            }
        )
    cards.append(
        {
            'title': '마을 현황',
            'subtitle': '현재 상태 요약',
            'lines': format_settlement_mood(snapshot),
        }
    )
    story_card = MVP_STORY_CARDS.get(snapshot.active_settlement_id, {}).get('archive')
    if story_card is not None:
        cards.insert(0, story_card)
    background_card = MVP_STORY_CARDS.get(snapshot.active_settlement_id, {}).get('square')
    if background_card is not None and _should_hide_square_story_card(snapshot):
        cards.append(
            {
                'title': '배경 설명',
                'subtitle': background_card['subtitle'],
                'lines': list(background_card['lines']),
            }
        )
    cards.extend(_build_quest_surface_cards(snapshot, 'archive'))
    return cards


def _quest_status(snapshot: WorldSnapshot) -> str:
    return snapshot.settlement_state.quest_status.get(MEDIATE_TAVERN_CONFLICT_QUEST_ID, 'not_started')


def _quest_penalty_ticks(snapshot: WorldSnapshot) -> int:
    return snapshot.settlement_state.quest_refusal_penalty_ticks.get(MEDIATE_TAVERN_CONFLICT_QUEST_ID, 0)


def _resident_status_for(snapshot: WorldSnapshot, settlement_id: str) -> str:
    settlement_state = snapshot.settlement_states.get(settlement_id)
    if settlement_state is None:
        return 'outsider'
    status = settlement_state.resident_status.get(settlement_id, 'outsider')
    if status == 'none':
        return 'outsider'
    if status == 'pending':
        return 'trusted_guest'
    if status == 'recognized':
        return 'resident'
    return status


def _resident_status(snapshot: WorldSnapshot) -> str:
    return _resident_status_for(snapshot, snapshot.active_settlement_id)


def _resident_status_label(snapshot: WorldSnapshot, settlement_id: str | None = None) -> str:
    return _resident_status_label_from_status(
        _resident_status_for(snapshot, settlement_id or snapshot.active_settlement_id),
        snapshot,
        settlement_id or snapshot.active_settlement_id,
    )


def _resident_status_label_from_status(
    status: str,
    snapshot: WorldSnapshot | None = None,
    settlement_id: str | None = None,
) -> str:
    labels = {
        'outsider': '낯선 이방인',
        'guest': '방문객',
        'trusted_guest': '신뢰받는 손님',
    }
    if status == 'resident':
        if snapshot is not None and settlement_id is not None:
            return f'{format_settlement_name(snapshot, settlement_id, short=True)} 주민'
        return '마을 주민'
    return labels.get(status, '낯선 이방인')


def _resident_status_line(snapshot: WorldSnapshot) -> str:
    status = _resident_status(snapshot)
    if status == 'resident':
        return '마을 사람들은 이제 당신을 안쪽 일까지 맡길 수 있는 사람으로 본다.'
    if status == 'trusted_guest':
        return '마을 사람들은 당신을 완전히 경계하지는 않지만, 아직 안쪽 일까지 맡기지는 않는다.'
    if status == 'guest':
        return '작은 일들을 도우며 마을 사람들의 시선이 조금 누그러졌다.'
    return '촌장은 아직 당신을 마을 사람으로 받아들이기엔 이르다고 판단한 듯하다.'


def _has_ethan_guarantee(snapshot: WorldSnapshot) -> bool:
    return snapshot.interaction_runtime_state.intro_dismissed or snapshot.interaction_runtime_state.tutorial_stage != 'talk_ethan'


def _build_resident_status_card(snapshot: WorldSnapshot) -> dict[str, Any]:
    return {
        'title': '현재 신분',
        'subtitle': _resident_status_label(snapshot),
        'lines': [
            _resident_status_line(snapshot),
            '회색언덕 주민증은 아직 물건이 아니라, 마을이 당신을 어떻게 보는지에 가깝다.',
        ],
    }


def _build_recognition_progress_card(snapshot: WorldSnapshot) -> dict[str, Any]:
    return {
        'title': '신뢰의 변화',
        'subtitle': _resident_status_label(snapshot),
        'lines': [
            '작은 일들을 도우며 마을 사람들의 시선이 조금 누그러졌다.',
            _resident_status_line(snapshot),
        ],
    }


def _has_mediation_problem(snapshot: WorldSnapshot) -> bool:
    state = snapshot.settlement_state
    if state.relationships.get(('blacksmith', 'farmer'), 0) < 0 or state.relationships.get(('farmer', 'blacksmith'), 0) < 0:
        return True
    farmer_states = state.npc_recent_states.get('farmer', [])
    blacksmith_states = state.npc_recent_states.get('blacksmith', [])
    return any(item.state_id == 'complaining_about_blacksmith' for item in farmer_states) and any(
        item.state_id == 'irritated_with_farmer' for item in blacksmith_states
    )


def _can_offer_mediation_problem(snapshot: WorldSnapshot) -> bool:
    status = _quest_status(snapshot)
    if status not in {'not_started', 'pending', 'refused'}:
        return False
    if status == 'refused' and _quest_penalty_ticks(snapshot) > 0:
        return False
    return _has_mediation_problem(snapshot)


def _build_mediation_offer_card(snapshot: WorldSnapshot) -> dict[str, Any]:
    return {
        'title': '촌장의 부탁',
        'subtitle': '마을 사람들의 말다툼',
        'lines': [
            '촌장이 조심스럽게 말을 꺼냈다.',
            '농부와 대장장이 사이가 더 나빠지기 전에 누군가 말을 좀 붙여줬으면 한다.',
            '이 문제에 개입할지 선택할 수 있다.',
        ],
        'actions': [
            {'label': '도와보겠다고 한다', 'payload': {'action_type': 'quest_decision', 'quest': 'mediation', 'decision': 'accept'}},
            {'label': '생각해보겠다고 한다', 'payload': {'action_type': 'quest_decision', 'quest': 'mediation', 'decision': 'defer'}, 'secondary': True},
            {'label': '거절한다', 'payload': {'action_type': 'quest_decision', 'quest': 'mediation', 'decision': 'refuse'}, 'secondary': True},
        ],
    }


def _build_active_mediation_card(snapshot: WorldSnapshot) -> dict[str, Any]:
    contacts = snapshot.settlement_state.quest_contacts.get(MEDIATE_TAVERN_CONFLICT_QUEST_ID, set())
    return {
        'title': '현재 신경 쓸 일',
        'subtitle': '마을 사람들의 말다툼',
        'lines': [
            '촌장이 농부와 대장장이 사이를 풀어볼 수 있겠냐고 부탁했다.',
            _resident_status_line(snapshot),
            f"{'☑' if 'farmer' in contacts else '□'} 농부와 이야기하기",
            f"{'☑' if 'blacksmith' in contacts else '□'} 대장장이와 이야기하기",
        ],
    }


def _build_deferred_mediation_card() -> dict[str, Any]:
    return {
        'title': '마을의 문제',
        'subtitle': '아직 남은 부탁',
        'lines': [
            '촌장은 고개를 끄덕였지만, 표정은 무거워 보였다.',
            '농부와 대장장이의 문제는 아직 해결되지 않았다.',
            '마음이 정리되면 다시 답할 수 있다.',
        ],
    }


def _build_refused_mediation_card(snapshot: WorldSnapshot) -> dict[str, Any]:
    if _quest_penalty_ticks(snapshot) > 0:
        lines = [
            '촌장은 아직 당신을 마을 사람으로 받아들이기엔 이르다고 판단한 듯하다.',
            '마을 사람들은 당신을 완전히 경계하지는 않지만, 아직 안쪽 일까지 맡기지는 않는다.',
            '마을의 갈등은 그대로 흘러가고 있다.',
        ]
    else:
        lines = [
            '작은 일들을 도우며 마을 사람들의 시선이 조금 누그러졌다.',
            '촌장은 아직 조심스럽지만, 다시 말을 꺼낼 준비가 된 듯하다.',
            '이번에는 다른 선택을 할 수 있다.',
        ]
    return {
        'title': '마을의 문제',
        'subtitle': '거절 뒤에 남은 거리',
        'lines': lines,
    }


def _build_completed_mediation_card() -> dict[str, Any]:
    return {
        'title': '플레이어의 흔적',
        'subtitle': '마을 사람들의 말다툼',
        'lines': [
            '플레이어는 농부와 대장장이 사이를 중재하려 했다.',
            '두 사람은 아직 어색하지만, 적어도 서로를 피하지는 않게 되었다.',
            '촌장은 당신을 회색언덕의 사람으로 인정했다.',
            '회색언덕 주민증을 받았다.',
        ],
    }


def _format_quest_lines(snapshot: WorldSnapshot) -> list[str]:
    status = _quest_status(snapshot)
    if status == 'active':
        contacts = snapshot.settlement_state.quest_contacts.get(MEDIATE_TAVERN_CONFLICT_QUEST_ID, set())
        return [
            '마을 사람들의 말다툼: 진행 중',
            f'현재 신분: {_resident_status_label(snapshot)}',
            f"{'완료' if 'farmer' in contacts else '남음'} - 농부와 이야기하기",
            f"{'완료' if 'blacksmith' in contacts else '남음'} - 대장장이와 이야기하기",
        ]
    if status == 'pending':
        return ['마을 사람들의 말다툼: 아직 답하지 않음', f'현재 신분: {_resident_status_label(snapshot)}']
    if status == 'refused':
        if _quest_penalty_ticks(snapshot) > 0:
            return ['마을 사람들의 말다툼: 거절 뒤 보류됨', f'현재 신분: {_resident_status_label(snapshot)}']
        return ['마을 사람들의 말다툼: 다시 이야기할 수 있음', f'현재 신분: {_resident_status_label(snapshot)}']
    if status == 'completed':
        return ['마을 사람들의 말다툼: 기록됨', f'현재 신분: {_resident_status_label(snapshot)}']
    return ['마을 사람들의 말다툼: 아직 맡은 일 없음', f'현재 신분: {_resident_status_label(snapshot)}']


def _build_quest_decision_result_card(decision: str) -> dict[str, Any]:
    if decision == 'accept':
        return {
            'title': '촌장의 부탁을 받았다',
            'subtitle': '마을 사람들의 말다툼',
            'lines': [
                '촌장이 안도한 듯 짧게 고개를 끄덕였다.',
                '마을 사람들은 아직 조심스럽지만, 당신에게 안쪽 일을 맡겨보기로 했다.',
                f'현재 신분: {_resident_status_label_from_status("trusted_guest")}',
                '이제 농부와 대장장이에게 각각 말을 붙여볼 차례다.',
            ],
        }
    if decision == 'defer':
        return {
            'title': '아직 답하지 않았다',
            'subtitle': '남아 있는 문제',
            'lines': [
                '촌장은 고개를 끄덕였지만, 표정은 무거워 보였다.',
                '이 문제는 아직 해결되지 않았다.',
            ],
        }
    return {
        'title': '부탁을 거절했다',
        'subtitle': '어색해진 거리',
        'lines': [
            '촌장은 잠시 말을 잃었다.',
            '마을 안쪽 일까지 맡기기엔 아직 이르다고 판단한 듯하다.',
        ],
    }


def _build_quest_surface_cards(snapshot: WorldSnapshot, surface: str) -> list[dict[str, Any]]:
    status = _quest_status(snapshot)
    cards: list[dict[str, Any]] = []
    if status == 'not_started' and _can_offer_mediation_problem(snapshot):
        cards.append(_build_mediation_offer_card(snapshot))
    elif status == 'active':
        cards.append(_build_active_mediation_card(snapshot))
    elif status == 'pending':
        cards.append(_build_deferred_mediation_card())
        if _can_offer_mediation_problem(snapshot):
            cards.append(_build_mediation_offer_card(snapshot))
    elif status == 'refused':
        cards.append(_build_refused_mediation_card(snapshot))
        if _quest_penalty_ticks(snapshot) == 0 and _has_mediation_problem(snapshot):
            cards.append(_build_mediation_offer_card(snapshot))
    elif status == 'completed' and surface == 'archive':
        cards.append(_build_completed_mediation_card())
    return cards


def _format_notice_line(notice: PlayerNotice) -> str:
    observer_name = NPC_NAME_BY_ID.get(notice.observer_npc_id, notice.observer_npc_id)
    if notice.notice_type == 'noticed_player_at_dawn':
        return f'{observer_name}이 새벽에 네 움직임을 눈여겨봤다.'
    return f'{observer_name}이 {notice.location}에서 이상한 낌새를 기억하고 있다.'


def _build_intro_card(snapshot: WorldSnapshot) -> dict[str, Any] | None:
    if snapshot.interaction_runtime_state.intro_dismissed:
        return None
    return {
        'title': '인트로',
        'subtitle': '낯선 세계에서 깨어나다',
        'lines': [
            '너는 회색언덕 마을 외곽에서 의식을 잃은 채 발견됐다.',
            '에단이 너를 업고 돌아왔고, 마을 사람들은 아직 너를 낯설게 본다.',
            '이곳에서는 직접 본 장면보다 소문과 기록이 먼저 세계의 윤곽을 드러낸다.',
        ],
        'actions': [
            {'label': '시작하기', 'payload': {'action_type': 'dismiss_intro'}},
        ],
    }


def _build_tutorial_card(snapshot: WorldSnapshot) -> dict[str, Any] | None:
    if snapshot.interaction_runtime_state.tutorial_completed:
        return None
    stage = snapshot.interaction_runtime_state.tutorial_stage
    stage_meta = TUTORIAL_STAGE_UI.get(stage, TUTORIAL_STAGE_UI['complete'])
    stage_index = min(TUTORIAL_STAGE_SEQUENCE.index(stage) + 1, len(TUTORIAL_STAGE_SEQUENCE)) if stage in TUTORIAL_STAGE_SEQUENCE else len(TUTORIAL_STAGE_SEQUENCE)
    progress_label = '완료' if snapshot.interaction_runtime_state.tutorial_completed else f'{stage_index}/{len(TUTORIAL_STAGE_SEQUENCE) - 1}'
    return {
        'title': stage_meta['title'],
        'subtitle': f"{stage_meta['subtitle']} | 진행 {progress_label}",
        'lines': list(stage_meta['lines']),
    }


def _append_unique_line(lines: list[str], value: str | None) -> None:
    if value and value not in lines:
        lines.append(value)


def _get_primary_narration_line(snapshot: WorldSnapshot) -> str | None:
    for dialogue in snapshot.presentation_state.dialogues:
        if dialogue.speaker_id == 'narrator' or dialogue.speaker_name == '나레이션':
            return _player_surface_text_or_none(snapshot, dialogue.text)
    if snapshot.presentation_state.visible_scenes:
        return _player_surface_text_or_none(snapshot, snapshot.presentation_state.visible_scenes[0])
    for event in snapshot.presentation_state.triggered_event_summaries:
        event_line = _player_surface_text_or_none(snapshot, event.outcome_text)
        if event_line is not None:
            return event_line
    return None


def _build_narration_card(snapshot: WorldSnapshot) -> dict[str, Any] | None:
    primary_line = _get_primary_narration_line(snapshot)
    if primary_line is None:
        return None
    return {
        'title': '나레이션',
        'subtitle': f"{snapshot.settlement_definition.flavor.title} | {snapshot.settlement_state.time_phase}",
        'lines': [primary_line],
    }


def _current_location_situation_lines(snapshot: WorldSnapshot) -> list[str]:
    location = snapshot.settlement_state.player_location
    if not location or location == '광장':
        return []

    location_lines = {
        '술집': [
            '술집 안에서는 공개 소문과 사람들의 목소리가 오간다.',
            '사람들이 흘리는 말 사이에서 마을의 분위기가 드러난다.',
        ],
        '뒷골목': [
            '밝은 자리에서는 잘 나오지 않는 이야기가 이곳에 고인다.',
            '발소리와 낮은 목소리가 골목 안쪽에서 얽힌다.',
        ],
        '기록관': [
            '기록관에는 사람들이 남긴 말과 사건의 흔적이 조용히 쌓인다.',
            '지금은 기록을 읽고 흐름을 정리하기 좋은 자리다.',
        ],
        '거점': [
            '에단의 짐이 놓인 작은 거점에서 하루를 정리할 수 있다.',
            '길을 떠날 준비와 휴식이 이곳에서 이어진다.',
        ],
        '시장': [
            '상인들의 목소리와 오가는 물건 사이로 시장의 기색이 드러난다.',
            '거래 이야기가 사람들의 표정을 바쁘게 만든다.',
        ],
        '치료소': [
            '치료소에는 여행자와 환자들이 남긴 낮은 목소리가 머문다.',
            '약재와 회복에 관한 이야기가 조심스럽게 오간다.',
        ],
        '대장간': [
            '대장간에는 쇠를 두드리는 소리와 짧은 소문이 함께 울린다.',
            '불빛과 연기 사이에서 사람들의 기색이 읽힌다.',
        ],
        '창고': [
            '창고 주변에는 물건을 나르는 발소리와 낮은 말들이 남는다.',
            '겉으로 드러나지 않는 움직임이 이곳에 쌓인다.',
        ],
    }
    lines = list(location_lines.get(location, [f'{location}에 머무르며 주변의 기색을 살피고 있다.']))
    lines.append(f'분위기: {_stress_label(snapshot.settlement_state.stress)}')
    return lines


def _build_situation_card(snapshot: WorldSnapshot) -> dict[str, Any]:
    lines: list[str] = _current_location_situation_lines(snapshot)
    if not lines:
        primary_narration = _get_primary_narration_line(snapshot)
        if primary_narration is not None:
            _append_unique_line(lines, f'나레이션: {primary_narration}')
        if snapshot.presentation_state.visible_scenes:
            _append_unique_line(lines, _player_surface_text_or_none(snapshot, snapshot.presentation_state.visible_scenes[0]))
        if snapshot.presentation_state.dialogues:
            dialogue = snapshot.presentation_state.dialogues[0]
            dialogue_text = _format_dialogue_text_for_player(snapshot, dialogue.speaker_id, dialogue.text)
            if dialogue_text is not None:
                _append_unique_line(lines, f'{dialogue.speaker_name}: {dialogue_text}')
        if snapshot.presentation_state.triggered_event_summaries:
            _append_unique_line(lines, _player_surface_text_or_none(snapshot, snapshot.presentation_state.triggered_event_summaries[0].outcome_text))
        lines = [line for line in lines if not _is_raw_state_entry_text(line)]
    if not lines:
        recent_entries = build_chronicle_query(snapshot).query_entries(settlement_id=snapshot.active_settlement_id, limit=2).entries
        lines.extend(filter_player_facing_entries(recent_entries, snapshot))
    if not lines:
        lines.extend(format_settlement_mood(snapshot))
    if not lines:
        lines.append('아직 눈에 띄는 움직임은 없다. 시간을 흘리거나 사람들과 말을 섞어 보자.')
    return {
        'title': '현재 상황',
        'subtitle': f"{snapshot.settlement_definition.flavor.title} | {snapshot.settlement_state.time_phase}",
        'lines': lines[:3],
    }


def _build_overview_cards(snapshot: WorldSnapshot) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    intro_card = _build_intro_card(snapshot)
    if intro_card is not None:
        cards.append(intro_card)
    cards.append(_build_situation_card(snapshot))
    tutorial_card = _build_tutorial_card(snapshot)
    if tutorial_card is not None:
        cards.append(tutorial_card)
    return cards


def _build_ui_sections(selected_facility_id: str) -> dict[str, bool]:
    return dict(FACILITY_CONTROL_VISIBILITY.get(selected_facility_id, FACILITY_CONTROL_VISIBILITY['square']))


def _build_available_interaction_choices(
    snapshot: WorldSnapshot,
    selected_facility_id: str,
) -> list[dict[str, str]]:
    # Player choices should be attached to concrete event cards, not exposed as
    # generic ambient buttons. Phase 8 engine choices still exist underneath.
    return []


def _build_npc_cards(snapshot: WorldSnapshot) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    fallback_role = snapshot.settlement_definition.flavor.npc_bias[0] if snapshot.settlement_definition.flavor.npc_bias else None
    for npc in snapshot.presentation_state.present_npcs:
        metadata = NPC_CARD_METADATA.get(
            npc.npc_id,
            {'role': fallback_role or npc.npc_id, 'personality': '침착함'},
        )
        recent_states = snapshot.settlement_state.npc_recent_states.get(npc.npc_id, [])
        npc_location = snapshot.settlement_state.npc_locations.get(npc.npc_id, snapshot.settlement_state.player_location or '광장')
        current_interest = recent_states[-1].state_id if recent_states else metadata.get('default_interest', f'{npc_location} 주변 상황')
        cards.append(
            {
                'npc_id': npc.npc_id,
                'name': npc.name,
                'role': metadata['role'],
                'personality': metadata['personality'],
                'current_interest': current_interest,
                'lines': [
                    f'현재 위치: {npc_location}',
                    f'최근 관련 기록: {current_interest}',
                ],
            }
        )
    return cards


def _build_facility_view(snapshot: WorldSnapshot, selected_facility_id: str) -> dict[str, Any]:
    settlement_state = snapshot.settlement_state
    flavor = snapshot.settlement_definition.flavor
    base_summary = _status_summary_lines(snapshot)
    view: dict[str, Any] = {
        'title': '광장',
        'description': flavor.summary or '정착지의 공기와 사람들의 움직임을 살피는 기본 화면이다.',
        'summary_lines': base_summary,
        'actions': [],
        'cards': [],
        'npc_cards': [],
    }

    if selected_facility_id == 'square':
        notices = [_format_notice_line(notice) for notice in settlement_state.player_notices[-3:]]
        narration_card = _build_narration_card(snapshot)
        view['title'] = '광장'
        view['description'] = flavor.summary or '최근 공지와 공개된 분위기를 살피고, 기본 행동을 선택한다.'
        view['summary_lines'] = base_summary
        view['actions'] = (
            [{'label': '광장으로 이동', 'payload': {'action_type': 'move', 'target_location': '광장'}}]
            if settlement_state.player_location != '광장'
            else [{'label': '기다리기', 'payload': {'action_type': 'wait'}}]
        )
        if (
            snapshot.interaction_runtime_state.tutorial_stage == 'talk_ethan'
            and settlement_state.player_location == '광장'
            and any(npc.npc_id == 'ethan' for npc in snapshot.presentation_state.present_npcs)
        ):
            view['actions'].insert(0, {'label': '에단과 대화하기', 'payload': {'action_type': 'talk', 'target_npc_id': 'ethan'}})
        if (
            snapshot.interaction_runtime_state.tutorial_stage == 'wait_in_square'
            and settlement_state.player_location == '광장'
        ):
            view['actions'] = [{'label': '광장에서 기다리기', 'payload': {'action_type': 'wait'}}]
        event_lines = [
            line
            for event in snapshot.presentation_state.triggered_event_summaries[:3]
            if (line := _player_surface_text_or_none(snapshot, event.outcome_text)) is not None
        ]
        view['cards'] = [
            {
                'title': '최근 사건',
                'subtitle': '공개된 움직임',
                'lines': event_lines or ['아직 공개된 사건이 없다.'],
            },
            {
                'title': '공지',
                'subtitle': '광장에서 들리는 말',
                'lines': notices[:3] or ['최근 공지가 없다.'],
            },
        ]
        view['cards'][1:1] = _build_quest_surface_cards(snapshot, 'square')
        story_card = MVP_STORY_CARDS.get(snapshot.active_settlement_id, {}).get('square')
        if story_card is not None and not _should_hide_square_story_card(snapshot):
            view['cards'].insert(0, story_card)
        if narration_card is not None:
            view['cards'].insert(0, narration_card)
        view['npc_cards'] = _build_npc_cards(snapshot)
    elif selected_facility_id == 'tavern':
        narration_card = _build_narration_card(snapshot)
        view['title'] = '술집'
        view['description'] = flavor.rumor_intro or '소문과 인물 대화가 모이는 곳이다. 세계 정보를 모으기에 좋다.'
        view['summary_lines'] = base_summary
        view['actions'] = (
            [{'label': '술집으로 이동', 'payload': {'action_type': 'move', 'target_location': '술집'}}]
            if settlement_state.player_location != '술집'
            else [
                {'label': '정보 수집', 'payload': {'action_type': 'gather_info'}},
                {'label': '기다리기', 'payload': {'action_type': 'wait'}},
            ]
        )
        view['cards'] = [
            {
                'title': '최근 소문',
                'subtitle': flavor.rumor_intro or '사람들이 주고받는 이야기',
                'lines': _build_rumor_briefing(snapshot, 'tavern'),
            }
        ]
        if narration_card is not None:
            view['cards'].insert(0, narration_card)
        view['npc_cards'] = _build_npc_cards(snapshot)
    elif selected_facility_id == 'back_alley':
        view['title'] = '뒷골목'
        view['description'] = '공식 기록에 남지 않는 숨은 소문과 수상한 움직임을 듣는 곳이다.'
        view['summary_lines'] = base_summary
        view['actions'] = [
            {'label': '수상한 소문 듣기', 'payload': {'action_type': 'gather_hidden_info'}},
            {'label': '낯선 인물 관찰', 'payload': {'action_type': 'gather_hidden_info'}},
            {'label': '단서 살피기', 'payload': {'action_type': 'gather_hidden_info'}},
            {'label': '기다리기', 'payload': {'action_type': 'wait'}},
        ]
        view['cards'] = [
            {
                'title': '숨은 소문',
                'subtitle': '공식 정보 밖에서 도는 말',
                'lines': _build_back_alley_rumor_lines(snapshot),
            }
        ]
    elif selected_facility_id == 'clinic':
        view['title'] = '치료소'
        view['description'] = '회복과 피로, 길 위에서 밀려온 사람들의 소식이 가장 먼저 닿는 곳이다.'
        view['summary_lines'] = base_summary
        view['actions'] = [
            {'label': '환자 살펴보기', 'payload': {'action_type': 'observe_clinic', 'topic': 'patients'}},
            {'label': '여행자 이야기 듣기', 'payload': {'action_type': 'observe_clinic', 'topic': 'travelers'}},
            {'label': '약재 상황 묻기', 'payload': {'action_type': 'observe_clinic', 'topic': 'herbs'}},
        ]
        view['cards'] = [
            {
                'title': '회복의 기척',
                'subtitle': '치료소 주변에서 오가는 말',
                'lines': _build_rumor_briefing(snapshot, 'clinic'),
            }
        ]
        view['npc_cards'] = _build_npc_cards(snapshot)
    elif selected_facility_id == 'market':
        view['title'] = '시장'
        view['description'] = '거래와 계약, 외부 방문객의 말이 가장 빨리 섞이는 곳이다.'
        view['summary_lines'] = base_summary
        view['actions'] = (
            [{'label': '시장으로 이동', 'payload': {'action_type': 'move', 'target_location': '시장'}}]
            if settlement_state.player_location != '시장'
            else [{'label': '기다리기', 'payload': {'action_type': 'wait'}}]
        )
        view['cards'] = [
            {
                'title': '장터의 말',
                'subtitle': '상인과 방문객이 남긴 이야기',
                'lines': _build_rumor_briefing(snapshot, 'market'),
            }
        ]
        view['npc_cards'] = _build_npc_cards(snapshot)
    elif selected_facility_id == 'archive':
        view['title'] = '기록관'
        view['description'] = flavor.archive_intro or '사건과 정착지의 흐름을 기록 단위로 읽는다.'
        view['summary_lines'] = base_summary
        view['actions'] = (
            [{'label': '기록관으로 이동', 'payload': {'action_type': 'move', 'target_location': '기록관'}}]
            if settlement_state.player_location != '기록관'
            else []
        )
        view['cards'] = _build_archive_cards(snapshot)
    elif selected_facility_id == 'base':
        recent_saves = list_recent_save_slots()
        save_lines = [
            f"슬롯 {item['slot']} | {format_time_for_player(snapshot, int(item['day']), int(item['tick']))} | {format_settlement_name(snapshot, str(item['active_settlement_id']))}"
            for item in recent_saves[:3]
        ] or ['최근 저장 기록이 없다.']
        view['title'] = '거점'
        view['description'] = '에단과 함께 지내는 작은 거점이다. 저장, 불러오기, 휴식, 현재 상태를 정리한다.'
        view['summary_lines'] = base_summary
        view['actions'] = (
            [{'label': '거점으로 이동', 'payload': {'action_type': 'move', 'target_location': '거점'}}]
            if settlement_state.player_location != '거점'
            else [
                {'label': '휴식', 'payload': {'action_type': 'wait'}},
                {'label': '저장', 'payload': {'client_action': 'save'}},
                {'label': '불러오기', 'payload': {'client_action': 'load'}},
                {'label': '리셋', 'payload': {'client_action': 'reset'}, 'secondary': True},
            ]
        )
        view['cards'] = [
            _build_resident_status_card(snapshot),
            {'title': '최근 저장 슬롯', 'subtitle': 'run 관리', 'lines': save_lines},
            {
                'title': '에단의 자리',
                'subtitle': '함께 머무는 사람',
                'lines': [
                    '거점 한쪽에는 에단이 남겨 둔 짐과 길 위에서 주워 온 낡은 끈이 놓여 있다.',
                    '그는 너와 함께 움직일 수도 있고, 네가 머무는 동안 혼자 마을 안팎을 살필 수도 있다.',
                    '최근에는 네 선택의 흔적이 조용히 이곳에 남아 있다.' if snapshot.interaction_runtime_state.last_choice_id else '아직 이곳에 따로 남은 선택의 흔적은 없다.',
                ],
            },
            {'title': '특수 인물 상태', 'subtitle': 'special NPC', 'lines': [f"{npc_id}: {state.status}" for npc_id, state in sorted(snapshot.special_npc_states.items())]},
        ]
        view['cards'][1:1] = _build_quest_surface_cards(snapshot, 'base')
    elif selected_facility_id == 'outside':
        destinations = [
            settlement_id
            for settlement_id in snapshot.settlement_definitions
            if can_travel_between_settlements(snapshot.active_settlement_id, settlement_id, snapshot.settlement_links)
        ]
        view['title'] = '도시 밖으로'
        view['description'] = '직접 연결된 다른 정착지로 걸어서 이동한다.'
        view['summary_lines'] = base_summary
        view['actions'] = [
            {
                'label': f'{format_settlement_name(snapshot, settlement_id)}로 이동',
                'payload': {'action_type': 'travel', 'target_settlement_id': settlement_id, 'travel_mode': 'walk'},
            }
            for settlement_id in destinations
        ]
        view['cards'] = [
            {
                'title': format_settlement_name(snapshot, settlement_id),
                'subtitle': '직접 연결됨',
                'lines': ['이동 수단: 도보', '다섯 차례 시간이 흐른다.'],
            }
            for settlement_id in destinations
        ] or [{'title': '이동 가능 경로 없음', 'subtitle': '현재 연결된 정착지가 없다.', 'lines': []}]
    if selected_facility_id != 'square':
        back_action = (
            {'label': '광장으로 돌아가기', 'payload': {'action_type': 'move', 'target_location': '광장'}, 'secondary': True}
            if settlement_state.player_location != '광장'
            else {'label': '돌아가기', 'payload': {'action_type': 'select_facility', 'facility_id': 'square'}, 'secondary': True}
        )
        view['actions'] = [
            *view['actions'],
            back_action,
        ]
    return view


class EngineSession:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.world_engine = build_world_engine()
        self.snapshot_state = create_default_world_snapshot()
        self.selected_facility_id = DEFAULT_FACILITY_ID
        self.shown_rumor_texts: set[str] = set()
        self.shown_hidden_rumor_texts: set[str] = set()

    def reset(self) -> dict[str, Any]:
        with self._lock:
            self.snapshot_state = reset_world_to_seed(self.world_engine)
            self.selected_facility_id = DEFAULT_FACILITY_ID
            self.shown_rumor_texts.clear()
            self.shown_hidden_rumor_texts.clear()
            return serialize_snapshot(self.snapshot_state, selected_facility_id=self.selected_facility_id)

    def save(self, slot: int) -> tuple[int, dict[str, Any]]:
        with self._lock:
            try:
                save_world_state_to_slot(self.snapshot_state, slot)
            except Exception:
                return HTTPStatus.BAD_REQUEST, {'error': '유효한 저장 슬롯(1-3)이 필요하다.'}
            return HTTPStatus.OK, serialize_snapshot(self.snapshot_state, selected_facility_id=self.selected_facility_id)

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
            self.selected_facility_id = _normalize_selected_facility(self.snapshot_state, self.selected_facility_id)
            self.shown_rumor_texts.clear()
            self.shown_hidden_rumor_texts.clear()
            return HTTPStatus.OK, serialize_snapshot(self.snapshot_state, selected_facility_id=self.selected_facility_id)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return serialize_snapshot(self.snapshot_state, selected_facility_id=self.selected_facility_id)

    def apply_action(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        with self._lock:
            if payload.get('action_type') == 'dismiss_intro':
                self.snapshot_state = rebuild_snapshot_surface(
                    self.snapshot_state,
                    interaction_runtime_state=dismiss_intro(self.snapshot_state.interaction_runtime_state),
                )
                return HTTPStatus.OK, serialize_snapshot(self.snapshot_state, selected_facility_id=self.selected_facility_id)
            if payload.get('action_type') == 'quest_decision':
                decision = payload.get('decision')
                if payload.get('quest') != 'mediation' or decision not in {'accept', 'defer', 'refuse'}:
                    return HTTPStatus.BAD_REQUEST, {'error': '선택할 수 없는 부탁이다.'}
                active_state = self.snapshot_state.settlement_state
                progress_system = self.world_engine.get_settlement_engine(
                    self.snapshot_state.active_settlement_id
                ).dialogue_system.player_progress_system
                if not progress_system.can_offer_mediation_quest(active_state):
                    return HTTPStatus.BAD_REQUEST, {'error': '지금은 그 부탁에 답할 수 없다.'}
                if decision == 'accept':
                    progress_system.accept_mediation_quest(active_state)
                elif decision == 'defer':
                    progress_system.defer_mediation_quest(active_state)
                else:
                    progress_system.refuse_mediation_quest(active_state)
                self.snapshot_state = rebuild_snapshot_surface(self.snapshot_state)
                return HTTPStatus.OK, serialize_snapshot(
                    self.snapshot_state,
                    selected_facility_id=self.selected_facility_id,
                    extra_overview_cards=[_build_quest_decision_result_card(str(decision))],
                )
            if payload.get('action_type') == 'gather_info':
                if self.selected_facility_id != 'tavern' or self.snapshot_state.settlement_state.player_location != '술집':
                    return HTTPStatus.BAD_REQUEST, {'error': '술집에서만 정보를 수집할 수 있다.'}
                response_payload = serialize_snapshot(self.snapshot_state, selected_facility_id=self.selected_facility_id)
                info_card = _dedupe_card_lines(
                    _build_tavern_info_result_card(self.snapshot_state),
                    self.shown_rumor_texts,
                    '더 건질 만한 새 이야기는 없어 보인다.',
                )
                response_payload['facility_view']['cards'] = [
                    info_card,
                    *response_payload['facility_view']['cards'],
                ]
                if info_card['lines'] == ['더 건질 만한 새 이야기는 없어 보인다.']:
                    for card in response_payload['facility_view']['cards'][1:]:
                        if card.get('title') == '최근 소문':
                            card['title'] = '최근 소문 (이미 들은 이야기)'
                            break
                return HTTPStatus.OK, response_payload
            if payload.get('action_type') == 'gather_hidden_info':
                if self.selected_facility_id != 'back_alley' or self.snapshot_state.settlement_state.player_location != '뒷골목':
                    return HTTPStatus.BAD_REQUEST, {'error': '뒷골목에서만 숨은 소문을 들을 수 있다.'}
                recognition_card = None
                if _quest_status(self.snapshot_state) == 'refused':
                    previous_status = _resident_status(self.snapshot_state)
                    previous_score = self.snapshot_state.settlement_state.recognition_score.get(self.snapshot_state.active_settlement_id, 0)
                    progress_system = self.world_engine.get_settlement_engine(
                        self.snapshot_state.active_settlement_id
                    ).dialogue_system.player_progress_system
                    progress_system.record_recognition_event(self.snapshot_state.settlement_state)
                    self.snapshot_state = rebuild_snapshot_surface(self.snapshot_state)
                    current_score = self.snapshot_state.settlement_state.recognition_score.get(self.snapshot_state.active_settlement_id, 0)
                    if current_score != previous_score or _resident_status(self.snapshot_state) != previous_status:
                        recognition_card = _build_recognition_progress_card(self.snapshot_state)
                response_payload = serialize_snapshot(self.snapshot_state, selected_facility_id=self.selected_facility_id)
                info_card = _dedupe_card_lines(
                    _build_back_alley_info_result_card(self.snapshot_state),
                    self.shown_hidden_rumor_texts,
                    '사람들은 같은 이야기를 되풀이하고 있다.',
                )
                response_payload['facility_view']['cards'] = [
                    *([recognition_card] if recognition_card is not None else []),
                    info_card,
                    *response_payload['facility_view']['cards'],
                ]
                return HTTPStatus.OK, response_payload
            if payload.get('action_type') == 'observe_clinic':
                if self.selected_facility_id != 'clinic':
                    return HTTPStatus.BAD_REQUEST, {'error': '치료소에서만 살펴볼 수 있다.'}
                response_payload = serialize_snapshot(self.snapshot_state, selected_facility_id=self.selected_facility_id)
                response_payload['facility_view']['cards'] = [
                    _build_clinic_observation_card(payload.get('topic') if isinstance(payload.get('topic'), str) else None),
                    *response_payload['facility_view']['cards'],
                ]
                return HTTPStatus.OK, response_payload
            if payload.get('action_type') == 'select_facility':
                facility_id = payload.get('facility_id')
                if not isinstance(facility_id, str):
                    return HTTPStatus.BAD_REQUEST, {'error': '유효한 시설이 필요하다.'}
                if not _can_access_facility_from_current_location(self.snapshot_state, facility_id):
                    return HTTPStatus.BAD_REQUEST, {'error': '지금 위치에서는 그 시설로 바로 들어갈 수 없다. 먼저 광장으로 나와야 한다.'}
                self.selected_facility_id = _normalize_selected_facility(self.snapshot_state, facility_id)
                self.snapshot_state = apply_tutorial_update(
                    self.snapshot_state,
                    selected_facility_id=self.selected_facility_id,
                )
                return HTTPStatus.OK, serialize_snapshot(self.snapshot_state, selected_facility_id=self.selected_facility_id)
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
            if (
                action.action_type == 'move'
                and settlement_state.player_location != '광장'
                and action.target_location != '광장'
            ):
                return HTTPStatus.BAD_REQUEST, {'error': '다른 시설을 보려면 먼저 광장으로 돌아가야 한다.'}
            available_choice_ids = {
                choice['choice_id']
                for choice in _build_available_interaction_choices(self.snapshot_state, self.selected_facility_id)
            }
            if action.action_type == 'choose' and action.choice_id not in available_choice_ids:
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
            if action.action_type == 'travel':
                self.selected_facility_id = DEFAULT_FACILITY_ID
                arrival_card = _build_travel_arrival_card(self.snapshot_state)
            else:
                self.selected_facility_id = _normalize_selected_facility(self.snapshot_state, self.selected_facility_id)
                self.snapshot_state = apply_tutorial_update(
                    self.snapshot_state,
                    selected_facility_id=self.selected_facility_id,
                )
                arrival_card = None
            return HTTPStatus.OK, serialize_snapshot(
                self.snapshot_state,
                selected_facility_id=self.selected_facility_id,
                extra_overview_cards=[arrival_card] if arrival_card is not None else None,
            )


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


def serialize_snapshot(
    snapshot: WorldSnapshot,
    selected_facility_id: str | None = None,
    extra_overview_cards: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    settlement_state = snapshot.settlement_state
    settlement_definition = snapshot.settlement_definition
    presentation_state = snapshot.presentation_state
    normalized_facility_id = _normalize_selected_facility(snapshot, selected_facility_id)
    facility_view = _build_facility_view(snapshot, normalized_facility_id)
    overview_cards = [*(extra_overview_cards or []), *_build_overview_cards(snapshot)]
    interaction_choices = _build_available_interaction_choices(snapshot, normalized_facility_id)
    ui_sections = _build_ui_sections(normalized_facility_id)
    ui_sections['choice'] = ui_sections['choice'] and bool(interaction_choices)
    chronicle_query = build_chronicle_query(snapshot)
    world_summary = build_world_summary_snapshot(snapshot)
    player_timeline = get_player_timeline(snapshot, limit=4)
    active_region_id = settlement_definition.region_id
    active_region_definition = snapshot.region_definitions.get(active_region_id)
    active_continent_id = active_region_definition.continent_id if active_region_definition is not None else None
    current_location = settlement_state.player_location or ''
    if current_location and current_location != '광장':
        available_locations = ['광장'] if '광장' in settlement_definition.locations else []
    else:
        available_locations = [location for location in settlement_definition.locations if location != '집']
    available_settlements = [
        settlement_id
        for settlement_id in snapshot.settlement_definitions
        if can_travel_between_settlements(snapshot.active_settlement_id, settlement_id, snapshot.settlement_links)
    ]
    available_settlement_options = [
        {'settlement_id': settlement_id, 'label': format_settlement_name(snapshot, settlement_id)}
        for settlement_id in available_settlements
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
    recent_saves = [
        {
            **item,
            'display_time': format_time_for_player(snapshot, int(item['day']), int(item['tick'])),
            'active_settlement_name': format_settlement_name(snapshot, str(item['active_settlement_id'])),
        }
        for item in list_recent_save_slots()
    ]
    facility_definitions = [facility for facility in settlement_definition.facilities if facility.enabled]
    if current_location and current_location != '광장':
        square_facility = next((facility for facility in facility_definitions if facility.facility_id == 'square'), None)
        facility_definitions = [square_facility] if square_facility is not None else []

    facilities = []
    for facility in facility_definitions:
        if not facility.enabled:
            continue
        accessible = _can_access_facility_from_current_location(snapshot, facility.facility_id)
        action_payload: dict[str, Any] = {'action_type': 'select_facility', 'facility_id': facility.facility_id}
        display_label = facility.label
        disabled = False
        if not accessible and facility.target_location is not None:
            display_label = f'{facility.label}으로 이동'
            action_payload = {'action_type': 'move', 'target_location': facility.target_location}
        elif not accessible and facility.facility_id != normalized_facility_id:
            disabled = True
        facilities.append(
            {
                'facility_id': facility.facility_id,
                'label': facility.label,
                'display_label': display_label,
                'facility_type': facility.facility_type,
                'enabled': facility.enabled,
                'accessible': accessible,
                'disabled': disabled,
                'access_hint': _facility_access_hint(snapshot, facility.facility_id),
                'action_payload': action_payload,
            }
        )
    facility_hints = [
        facility['access_hint']
        for facility in facilities
        if facility['access_hint']
    ][:4]
    special_npc_state_lines = [
        f"{npc_id}: {state.status} ({state.linked_settlement_id or 'unlinked'})"
        for npc_id, state in sorted(snapshot.special_npc_states.items())
    ]
    chronicle_highlights = filter_player_facing_entries(settlement_result.entries[:3], snapshot) or ['아직 정리된 기록이 없다.']
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
        'active_settlement_name': format_settlement_name(snapshot, snapshot.active_settlement_id),
        'day': settlement_state.day,
        'tick': settlement_state.tick,
        'display_time': _format_day_phase_for_player(snapshot, settlement_state.day, settlement_state.time_phase),
        'time_phase': settlement_state.time_phase,
        'player_location': settlement_state.player_location,
        'settlement_flavor_title': settlement_definition.flavor.title,
        'settlement_flavor_summary': settlement_definition.flavor.summary,
        'overview_cards': overview_cards,
        'facilities': facilities,
        'facility_hints': facility_hints,
        'selected_facility_id': normalized_facility_id,
        'facility_view': facility_view,
        'ui_sections': ui_sections,
        'available_locations': available_locations,
        'available_settlements': available_settlements,
        'available_settlement_options': available_settlement_options,
        'present_npcs': [
            {'npc_id': npc.npc_id, 'name': npc.name}
            for npc in presentation_state.present_npcs
        ],
        'visible_scenes': [
            line
            for scene in presentation_state.visible_scenes
            if (line := _player_surface_text_or_none(snapshot, scene)) is not None
        ],
        'dialogues': [
            {'speaker_id': dialogue.speaker_id, 'speaker_name': dialogue.speaker_name, 'text': text}
            for dialogue in presentation_state.dialogues
            if (text := _format_dialogue_text_for_player(snapshot, dialogue.speaker_id, dialogue.text)) is not None
        ],
        'triggered_events': [
            {'event_id': event.event_id, 'outcome_text': line}
            for event in presentation_state.triggered_event_summaries
            if (line := _player_surface_text_or_none(snapshot, event.outcome_text)) is not None
        ],
        'rumor_lines': filter_player_facing_entries(presentation_state.rumor_lines, snapshot),
        'chronicle_highlights': chronicle_highlights,
        'quests': _format_quest_lines(snapshot),
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
