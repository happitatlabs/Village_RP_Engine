from __future__ import annotations

from village_rp_engine.models.player_action import PlayerAction


LOCATION_ALIASES: dict[str, str] = {
    '광장': '광장',
    'square': '광장',
    '대장간': '대장간',
    'smithy': '대장간',
    '술집': '술집',
    'tavern': '술집',
    'bar': '술집',
    '창고': '창고',
    'warehouse': '창고',
    '시장': '시장',
    'market': '시장',
}

NPC_ALIASES: dict[str, str] = {
    'guard_captain': 'guard_captain',
    'guard captain': 'guard_captain',
    'captain': 'guard_captain',
    '경비대장': 'guard_captain',
    'village_elder': 'village_elder',
    'village elder': 'village_elder',
    'elder': 'village_elder',
    '촌장': 'village_elder',
    'blacksmith': 'blacksmith',
    'smith': 'blacksmith',
    '대장장이': 'blacksmith',
    'farmer': 'farmer',
    '농부': 'farmer',
    'innkeeper': 'innkeeper',
    '여관주인': 'innkeeper',
}

SETTLEMENT_ALIASES: dict[str, str] = {
    'village_1': 'village_1',
    'village 1': 'village_1',
    '마을1': 'village_1',
    'village_2': 'village_2',
    'village 2': 'village_2',
    '마을2': 'village_2',
    'town_1': 'town_1',
    'town 1': 'town_1',
    'town': 'town_1',
    '소도시1': 'town_1',
}

WAIT_ALIASES = {'wait', '대기', ''}
MOVE_PREFIXES = ('move ', '이동 ')
TALK_PREFIXES = ('talk ', '대화 ')
TRAVEL_PREFIXES = ('travel ', '여행 ')
CHOICE_PREFIXES = ('choose ', '선택 ')
MOVE_SUFFIX = '가기'
MOVE_POSTFIX = '이동'
TALK_SUFFIXES = ('말걸기', '대화')
TALK_PREFIX = '말걸기 '


def _normalize_whitespace(raw: str) -> str:
    return ' '.join(raw.strip().split())


def normalize_location_alias(raw_target: str) -> str | None:
    normalized = _normalize_whitespace(raw_target)
    if not normalized:
        return None
    return LOCATION_ALIASES.get(normalized.lower())


def normalize_npc_alias(raw_target: str) -> str | None:
    normalized = _normalize_whitespace(raw_target)
    if not normalized:
        return None
    return NPC_ALIASES.get(normalized.lower())


def normalize_settlement_alias(raw_target: str) -> str | None:
    normalized = _normalize_whitespace(raw_target)
    if not normalized:
        return None
    return SETTLEMENT_ALIASES.get(normalized.lower())


def normalize_talk_target(raw_target: str) -> str:
    normalized = normalize_npc_alias(raw_target)
    return normalized or _normalize_whitespace(raw_target).replace(' ', '_')


def parse_player_input(raw: str) -> PlayerAction | None:
    normalized = _normalize_whitespace(raw)
    lowered = normalized.lower()

    if lowered in WAIT_ALIASES:
        return PlayerAction.wait()

    for prefix in TRAVEL_PREFIXES:
        if lowered.startswith(prefix):
            settlement_id = normalize_settlement_alias(normalized[len(prefix):])
            return PlayerAction.travel(settlement_id) if settlement_id else None

    for prefix in MOVE_PREFIXES:
        if lowered.startswith(prefix):
            location = normalize_location_alias(normalized[len(prefix):])
            return PlayerAction.move(location) if location else None

    for prefix in CHOICE_PREFIXES:
        if lowered.startswith(prefix):
            choice_id = _normalize_whitespace(normalized[len(prefix):]).lower().replace(' ', '_')
            return PlayerAction.choose(choice_id) if choice_id else None

    if normalized.endswith(MOVE_SUFFIX):
        location = normalize_location_alias(normalized[:-len(MOVE_SUFFIX)])
        return PlayerAction.move(location) if location else None

    if normalized.endswith(MOVE_POSTFIX):
        location = normalize_location_alias(normalized[:-len(MOVE_POSTFIX)])
        return PlayerAction.move(location) if location else None

    for prefix in TALK_PREFIXES:
        if lowered.startswith(prefix):
            npc_id = normalize_npc_alias(normalized[len(prefix):])
            return PlayerAction.talk(npc_id) if npc_id else None

    if lowered.startswith(TALK_PREFIX):
        npc_id = normalize_npc_alias(normalized[len(TALK_PREFIX):])
        return PlayerAction.talk(npc_id) if npc_id else None

    for suffix in TALK_SUFFIXES:
        if normalized.endswith(suffix):
            npc_id = normalize_npc_alias(normalized[:-len(suffix)])
            return PlayerAction.talk(npc_id) if npc_id else None

    return None
