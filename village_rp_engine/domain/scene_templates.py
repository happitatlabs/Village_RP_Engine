from __future__ import annotations

from village_rp_engine.korean import with_particle
from village_rp_engine.models.event import TriggeredEvent


EVENT_SCENE_TEMPLATES: dict[str, dict[str, object]] = {
    "argument_at_tavern": {
        "rp": {
            "entry": [
                "네가 술집 안으로 들어서자, {actor1_subject} 잔을 탁 내려놓으며 {actor2}에게 날카롭게 쏘아붙이고 있었다.",
                "네가 술집에 발을 들이자, {actor1}와 {actor2}가 서로를 향해 날 선 말을 주고받고 있었다.",
            ],
            "observe": [
                "술집 안에서는 {actor1}와 {actor2}가 서로를 향해 언성을 높이고 있었다.",
                "술집 공기가 거칠게 흔들렸다. 네 눈앞에서 {actor1}와 {actor2}가 서로를 향해 언성을 높이고 있었다.",
            ],
        },
        "observer": [
            "술집에서 {actor1}와 {actor2}가 거칠게 언성을 높이고 있었다.",
            "술집 안에서는 {actor1}와 {actor2} 사이에 팽팽한 말다툼이 벌어지고 있었다.",
        ],
    },
    "morning_chat_square": {
        "rp": {
            "entry": [
                "네가 광장에 이르렀을 때, {actor1_topic} 사람들과 아침 공기 속에서 한가로운 이야기를 나누고 있었다.",
                "광장에 들어서자, {actor1_topic} 사람들 사이에 섞여 느긋한 아침 이야기를 이어가고 있는 모습이 눈에 들어왔다.",
            ],
            "observe": [
                "광장에서는 {actor1}가 사람들 사이에 섞여 느긋한 아침 이야기를 이어가고 있었다.",
                "네 앞에서 {actor1_topic} 사람들과 한가로운 아침 이야기를 나누고 있었다.",
            ],
        },
        "observer": [
            "광장에서 {actor1}가 사람들과 아침 이야기를 나누고 있었다.",
            "아침 광장에서는 {actor1}가 사람들 틈에서 느긋한 대화를 이어가고 있었다.",
        ],
    },
    "farmer_grumbling_square": {
        "rp": {
            "entry": [
                "네가 광장에 이르렀을 때, 농부는 어젯밤 소란을 곱씹으며 못마땅한 기색으로 투덜거리고 있었다.",
                "광장에 들어서자, 농부는 사람들 앞에서 어젯밤 일에 대한 불만을 숨기지 않고 있었다.",
            ],
            "observe": [
                "광장에서는 농부가 어젯밤 소란을 떠올리며 불만스러운 목소리로 투덜거리고 있었다.",
                "네 앞에서 농부는 어젯밤 말다툼을 곱씹듯 못마땅한 말을 늘어놓고 있었다.",
            ],
        },
        "observer": [
            "광장에서 농부가 어젯밤 소란을 떠올리며 불만 섞인 말을 이어가고 있었다.",
            "농부는 광장에서 어젯밤 일을 두고 못마땅한 반응을 드러내고 있었다.",
        ],
    },
    "late_night_cleanup": {
        "rp": {
            "entry": [
                "네가 술집 안을 둘러보자, {actor1_topic} 남은 잔을 천천히 정리하고 있었다.",
                "하루가 거의 끝난 술집 안으로 들어서니, {actor1_topic} 조용히 의자와 잔을 정돈하며 마무리를 하고 있었다.",
            ],
            "observe": [
                "늦은 밤 술집 안은 한산했고, {actor1_topic} 남은 잔을 천천히 정리하고 있었다.",
                "하루가 거의 끝난 술집 안에서, {actor1_topic} 조용히 의자와 잔을 정돈하며 마무리를 하고 있었다.",
            ],
        },
        "observer": [
            "늦은 밤 술집에서 {actor1}가 조용히 가게를 정리하고 있었다.",
            "술집 안에서는 {actor1}가 하루를 마무리하며 잔과 의자를 정돈하고 있었다.",
        ],
    },
}

NOTICE_SCENE_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "default": {
        "rp": [
            "{actor1_subject} 네 쪽을 한 번 힐끗 보고는 아무 말 없이 시선을 거두었다.",
        ],
        "observer": [
            "{actor1}가 플레이어를 잠시 눈여겨보았다.",
        ],
    },
    "guard_captain": {
        "rp": [
            "경비대장이 네 쪽을 한 번 훑어보았다.",
        ],
        "observer": [
            "경비대장이 플레이어를 경계하듯 짧게 살폈다.",
        ],
    },
    "village_elder": {
        "rp": [
            "촌장의 시선이 잠시 네게 머물렀다가 거두어졌다.",
        ],
        "observer": [
            "촌장이 플레이어를 잠시 눈여겨보았다.",
        ],
    },
}


ARRIVAL_SCENE_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "술집": {
        "rp": [
            "술집 문이 열리며 {actor1_subject} 안으로 들어왔다.",
            "잠시 뒤 {actor1_subject} 술집 안으로 들어와 주변을 훑어보았다.",
        ],
        "observer": [
            "술집으로 {actor1}가 들어왔다.",
            "플레이어가 있는 술집에 {actor1}가 새로 들어왔다.",
        ],
    },
    "광장": {
        "rp": [
            "잠시 뒤 {actor1_subject} 광장 쪽에서 걸어 들어오는 모습이 보였다.",
            "네가 있는 광장으로 {actor1_subject} 천천히 발걸음을 옮겨왔다.",
        ],
        "observer": [
            "광장으로 {actor1}가 새로 들어왔다.",
            "플레이어가 있는 광장에 {actor1}가 합류했다.",
        ],
    },
    "대장간": {
        "rp": [
            "대장간 문턱 너머로 {actor1_subject} 안으로 들어왔다.",
            "잠시 뒤 {actor1_subject} 대장간 안으로 들어와 작업대를 향해 걸었다.",
        ],
        "observer": [
            "대장간으로 {actor1}가 들어왔다.",
            "플레이어가 있는 대장간에 {actor1}가 새로 들어왔다.",
        ],
    },
    "뒷골목": {
        "rp": [
            "좁은 길 끝에서 {actor1_subject} 조심스럽게 모습을 드러냈다.",
            "잠시 뒤 {actor1_subject} 뒷골목 안쪽으로 발걸음을 옮겼다.",
        ],
        "observer": [
            "뒷골목으로 {actor1}가 들어왔다.",
            "플레이어가 있는 뒷골목에 {actor1}가 모습을 드러냈다.",
        ],
    },
}

GUARD_CAPTAIN_NOTICE_SCENE_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "default": {
        "rp": [
            "{actor1_subject} 네 쪽을 한 번 힐끗 보고는 아무 말 없이 시선을 거두었다.",
        ],
        "observer": [
            "{actor1}가 플레이어를 잠시 눈여겨보았다.",
        ],
    },
    "guard_captain": {
        "rp": [
            "경비대장이 네 쪽을 한 번 훑어보았다.",
        ],
        "observer": [
            "경비대장이 플레이어를 경계하듯 짧게 살폈다.",
        ],
    },
    "village_elder": {
        "rp": [
            "촌장의 시선이 잠시 네게 머물렀다가 거두어졌다.",
        ],
        "observer": [
            "촌장이 플레이어를 잠시 눈여겨보았다.",
        ],
    },
}


GUARD_CAPTAIN_ARRIVAL_SCENE_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "술집": {
        "rp": [
            "경비대장이 입구에서 안쪽을 훑어본 뒤 술집 안으로 들어왔다.",
            "잠시 뒤 경비대장이 술집 안으로 들어서며 주변을 재빨리 살폈다.",
        ],
        "observer": [
            "경비대장이 술집 안으로 들어와 주변을 경계하듯 살폈다.",
            "술집으로 들어온 경비대장이 내부를 짧게 점검하듯 둘러보았다.",
        ],
    },
    "광장": {
        "rp": [
            "경비대장이 네 쪽으로 시선을 던진 채 광장으로 걸어 들어왔다.",
            "잠시 뒤 경비대장이 광장에 들어서며 주변을 재빨리 훑어보았다.",
        ],
        "observer": [
            "경비대장이 광장에 들어서며 주변을 경계하듯 살폈다.",
            "광장으로 들어온 경비대장이 사람들 움직임을 빠르게 확인했다.",
        ],
    },
    "대장간": {
        "rp": [
            "경비대장이 대장간 안으로 들어오며 작업장 구석까지 빠르게 훑어보았다.",
            "잠시 뒤 경비대장이 대장간 안에 발을 들이며 주변을 경계하듯 살폈다.",
        ],
        "observer": [
            "경비대장이 대장간으로 들어와 내부를 짧게 점검하듯 둘러보았다.",
            "대장간에 들어선 경비대장이 주변을 경계하는 눈으로 살폈다.",
        ],
    },
    "시장": {
        "rp": [
            "시장 입구 쪽에서 {actor1_subject} 오가는 사람들 사이를 살피고 있었다.",
            "네가 시장으로 들어서자, {actor1_subject} 좌판 사이를 천천히 훑어보고 있었다.",
        ],
        "observer": [
            "시장에서는 {actor1_subject} 오가는 사람들 틈에서 주변을 살피고 있었다.",
            "시장 한쪽에서 {actor1_subject} 사람들 움직임을 느긋하게 바라보고 있었다.",
        ],
    },
    "뒷골목": {
        "rp": [
            "뒷골목 어귀에서 경비대장이 잠시 발걸음을 멈추고 주변을 살폈다.",
            "경비대장이 좁은 길 안쪽을 훑으며 천천히 들어왔다.",
        ],
        "observer": [
            "경비대장이 뒷골목으로 들어와 주변을 살폈다.",
            "뒷골목에 들어선 경비대장이 어두운 구석을 확인했다.",
        ],
    },
}

IDLE_SCENE_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "술집": {
        "rp": [
            "네가 술집 안을 둘러보자, {actor1_subject} 잔을 닦으며 손님 맞을 준비를 하고 있었다.",
            "술집 안에는 잔 냄새가 은근히 맴돌았고, 네 눈앞에는 {actor1_subject} 조용히 자리를 정돈하는 모습이 보였다.",
        ],
        "observer": [
            "술집에서는 {actor1_subject} 잔을 닦으며 자리를 정돈하고 있었다.",
            "술집 안에는 {actor1_subject} 손님 맞을 준비를 하고 있었다.",
        ],
    },
    "대장간": {
        "rp": [
            "네가 대장간에 들어서자, {actor1_subject} 작업대를 살피며 하루 일을 준비하고 있었다.",
            "대장간 안에 발을 들이자, {actor1_subject} 망치와 집게를 가다듬으며 일손을 정리하고 있었다.",
        ],
        "observer": [
            "대장간에서는 {actor1_subject} 작업대를 살피며 하루 일을 준비하고 있었다.",
            "대장간 안에서는 {actor1_subject} 연장들을 정돈하며 작업을 준비하고 있었다.",
        ],
    },
    "광장": {
        "rp": [
            "광장에 들어서자, {actor1_subject} 주변을 둘러보며 한가롭게 서 있는 모습이 눈에 들어왔다.",
            "네가 광장으로 나서자, {actor1_subject} 느긋한 표정으로 사람들 사이를 살피고 있었다.",
        ],
        "observer": [
            "광장에서는 {actor1_subject} 주변을 둘러보며 서 있었다.",
            "광장 한쪽에서 {actor1_subject} 사람들 오가는 모습을 느긋하게 살피고 있었다.",
        ],
    },
    "시장": {
        "rp": [
            "시장 안으로 들어서자, {actor1_subject} 붐비는 좌판 사이를 둘러보고 있었다.",
            "시장 한쪽에서는 {actor1_subject} 사람들 흐름을 살피며 자리를 지키고 있었다.",
        ],
        "observer": [
            "시장에서는 {actor1_subject} 붐비는 사람들 틈에서 주변을 살피고 있었다.",
            "시장 한쪽에서 {actor1_subject} 좌판 사이를 느긋하게 둘러보고 있었다.",
        ],
    },
    "뒷골목": {
        "rp": [
            "뒷골목 안쪽에서 {actor1_subject} 주변 눈치를 살피고 있었다.",
            "좁은 길목에 {actor1_subject} 조용히 서서 지나가는 말을 듣고 있었다.",
        ],
        "observer": [
            "뒷골목에서 {actor1}가 주변을 조용히 살피고 있었다.",
            "{actor1}가 뒷골목 한쪽에서 말을 아끼고 있었다.",
        ],
    },
}

GUARD_CAPTAIN_IDLE_SCENE_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "술집": {
        "rp": [
            "네가 술집 안을 둘러보자, 경비대장이 주변 손님들을 경계하듯 살피고 있었다.",
            "네 앞에서 경비대장은 잠시도 방심하지 않는 눈으로 술집 안을 훑고 있었다.",
        ],
        "observer": [
            "술집 안에서 경비대장이 주변을 경계하듯 살피고 있었다.",
            "경비대장은 술집 안을 점검하듯 둘러보며 자리를 지키고 있었다.",
        ],
    },
    "광장": {
        "rp": [
            "광장 한쪽에서 경비대장이 주변을 날카롭게 살피고 있었다.",
            "경비대장이 광장에 서서 오가는 사람들을 경계하듯 훑어보고 있었다.",
        ],
        "observer": [
            "광장 한쪽에서 경비대장이 주변을 경계하듯 살피고 있었다.",
            "경비대장은 광장에서 사람들 움직임을 놓치지 않으려는 듯 주시하고 있었다.",
        ],
    },
    "대장간": {
        "rp": [
            "네가 대장간에 들어서자, 경비대장이 내부를 점검하듯 둘러보고 있었다.",
            "대장간 안에서 경비대장은 주변을 경계하는 눈으로 작업장을 살피고 있었다.",
        ],
        "observer": [
            "대장간 안에서 경비대장이 내부를 경계하듯 둘러보고 있었다.",
            "경비대장은 대장간 내부를 살피며 이상이 없는지 확인하고 있었다.",
        ],
    },
    "시장": {
        "rp": [
            "시장 안에서 경비대장이 붐비는 좌판 사이를 경계하듯 살피고 있었다.",
            "경비대장이 시장으로 들어서며 오가는 사람들을 빠르게 훑어보았다.",
        ],
        "observer": [
            "시장에서는 경비대장이 사람들 흐름을 경계하듯 살피고 있었다.",
            "시장 안으로 들어온 경비대장이 좌판 주변을 점검하듯 둘러보았다.",
        ],
    },
    "뒷골목": {
        "rp": [
            "뒷골목 한쪽에서 경비대장이 어두운 구석을 경계하듯 살피고 있었다.",
            "경비대장은 좁은 길목을 지나며 주변 기척을 놓치지 않으려 했다.",
        ],
        "observer": [
            "뒷골목에서 경비대장이 주변을 경계하듯 살피고 있었다.",
            "경비대장이 뒷골목 안쪽을 조심스럽게 확인하고 있었다.",
        ],
    },
}


def render_event_scene(
    event: TriggeredEvent,
    tick: int,
    npc_names: dict[str, str],
    player_moved: bool,
) -> tuple[str, str]:
    context = build_context(event.actor_ids, npc_names)
    rp_context = "entry" if player_moved else "observe"
    rp_templates = EVENT_SCENE_TEMPLATES[event.event_id]["rp"][rp_context]
    rp_text = select_template(rp_templates, tick).format_map(context)
    observer_text = select_template(EVENT_SCENE_TEMPLATES[event.event_id]["observer"], tick).format_map(context)
    return rp_text, observer_text


def render_arrival_scene(location: str, npc_id: str, tick: int, npc_names: dict[str, str]) -> tuple[str, str]:
    context = build_context((npc_id,), npc_names)
    template_source = GUARD_CAPTAIN_ARRIVAL_SCENE_TEMPLATES if npc_id == "guard_captain" else ARRIVAL_SCENE_TEMPLATES
    location_templates = template_source.get(location, ARRIVAL_SCENE_TEMPLATES.get(location, ARRIVAL_SCENE_TEMPLATES["광장"]))
    rp_text = select_template(location_templates["rp"], tick).format_map(context)
    observer_text = select_template(location_templates["observer"], tick).format_map(context)
    return rp_text, observer_text


def render_idle_scene(location: str, npc_id: str, tick: int, npc_names: dict[str, str]) -> tuple[str, str]:
    context = build_context((npc_id,), npc_names)
    template_source = GUARD_CAPTAIN_IDLE_SCENE_TEMPLATES if npc_id == "guard_captain" else IDLE_SCENE_TEMPLATES
    location_templates = template_source.get(location, IDLE_SCENE_TEMPLATES.get(location, IDLE_SCENE_TEMPLATES["광장"]))
    rp_text = select_template(location_templates["rp"], tick).format_map(context)
    observer_text = select_template(location_templates["observer"], tick).format_map(context)
    return rp_text, observer_text


def render_notice_scene(npc_id: str, tick: int, npc_names: dict[str, str]) -> tuple[str, str]:
    context = build_context((npc_id,), npc_names)
    template_source = NOTICE_SCENE_TEMPLATES.get(npc_id, NOTICE_SCENE_TEMPLATES["default"])
    rp_text = select_template(template_source["rp"], tick).format_map(context)
    observer_text = select_template(template_source["observer"], tick).format_map(context)
    return rp_text, observer_text


def select_template(templates: list[str], tick: int) -> str:
    return templates[(tick - 1) % len(templates)]


def build_context(actor_ids: tuple[str, ...], npc_names: dict[str, str]) -> dict[str, str]:
    names = [npc_names.get(actor_id, actor_id) for actor_id in actor_ids]
    context: dict[str, str] = {}
    if names:
        context["actor1"] = names[0]
        context["actor1_subject"] = with_particle(names[0], "이/가")
        context["actor1_topic"] = with_particle(names[0], "은/는")
    if len(names) > 1:
        context["actor2"] = names[1]
        context["actor2_subject"] = with_particle(names[1], "이/가")
        context["actor2_topic"] = with_particle(names[1], "은/는")
    return context
