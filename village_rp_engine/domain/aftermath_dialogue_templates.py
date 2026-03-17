from __future__ import annotations

AFTERMATH_DIALOGUE_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "farmer": {
        "complaining_about_blacksmith": [
            "어젯밤 일은 아직도 기분이 나쁘군.",
            "대장장이랑은 한동안 말 섞기 싫어.",
        ]
    },
    "blacksmith": {
        "irritated_with_farmer": [
            "쓸데없는 시비는 질색이야.",
            "괜한 말이 너무 많아.",
        ]
    },
    "village_elder": {
        "concerned_about_tavern_argument": [
            "어젯밤 소란은 그냥 넘길 일이 아니네.",
            "마을 안 다툼은 오래 남는 법이지.",
            "괜한 말다툼이 커지지 않도록 봐야겠군.",
        ]
    },
    "guard_captain": {
        "watchful_after_tavern_argument": [
            "또 소란이 생기면 이번엔 그냥 넘기지 않겠다.",
            "한동안 술집 쪽은 더 지켜봐야겠군.",
            "질서는 무너지기 시작하면 순식간이다.",
        ]
    },
}
