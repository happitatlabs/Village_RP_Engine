from __future__ import annotations

EVENT_DIALOGUE_TEMPLATES: dict[str, list[list[dict[str, str]]]] = {
    "argument_at_tavern": [
        [
            {"speaker": "blacksmith", "text": "또 그 소리냐?"},
            {"speaker": "farmer", "text": "내가 틀린 말 했나?"},
        ],
        [
            {"speaker": "blacksmith", "text": "괜한 소문 퍼뜨리지 마."},
            {"speaker": "farmer", "text": "네가 먼저 시작했잖아."},
        ],
    ],
    "morning_chat_square": [
        [
            {"speaker": "farmer", "text": "오늘 아침 공기는 괜찮군."},
        ],
        [
            {"speaker": "farmer", "text": "해가 빨리 올라오네."},
        ],
    ],
    "farmer_grumbling_square": [
        [
            {"speaker": "farmer", "text": "어젯밤 일은 아직도 기분이 나쁘군."},
        ],
        [
            {"speaker": "farmer", "text": "대장장이랑은 한동안 말 섞기 싫어."},
        ],
    ],
    "late_night_cleanup": [
        [
            {"speaker": "innkeeper", "text": "오늘도 겨우 끝났군."},
        ],
        [
            {"speaker": "innkeeper", "text": "이제 좀 조용해졌네."},
        ],
    ],
}
