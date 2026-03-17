from __future__ import annotations

from village_rp_engine.models.event import EventDefinition


def build_event_definitions() -> list[EventDefinition]:
    return [
        EventDefinition(
            event_id="argument_at_tavern",
            time_phase="저녁",
            location="술집",
            required_actor_ids=("blacksmith", "farmer"),
            outcome_text="대장장이와 농부가 술집에서 말다툼을 벌였다.",
            rumor_text="술집에서 대장장이와 농부가 언성을 높였다는 소문이 퍼졌다.",
            narration_text="네가 술집에 들어섰을 때, 대장장이와 농부가 날카롭게 언성을 높이고 있었다.",
            observer_narration_text="술집에서 대장장이와 농부가 날카롭게 언성을 높이고 있었다.",
            probability=1.0,
            cooldown_tick=2,
            rumor_base_score=2,
        ),
        EventDefinition(
            event_id="morning_chat_square",
            time_phase="아침",
            location="광장",
            required_actor_ids=("farmer",),
            outcome_text="농부가 광장에서 사람들과 아침 이야기를 나눴다.",
            rumor_text="광장에서 농부가 아침 이야기를 나눴다는 소문이 돌았다.",
            narration_text="네가 광장에 도착했을 때, 농부가 사람들과 한가롭게 아침 이야기를 나누고 있었다.",
            observer_narration_text="광장에서 농부가 사람들과 한가롭게 아침 이야기를 나누고 있었다.",
            probability=1.0,
            cooldown_tick=1,
            rumor_base_score=0,
        ),
        EventDefinition(
            event_id="late_night_cleanup",
            time_phase="밤",
            location="술집",
            required_actor_ids=("innkeeper",),
            outcome_text="여관주인이 늦은 밤 술집을 정리했다.",
            rumor_text="늦은 밤에도 여관주인이 술집을 정리했다는 말이 돌았다.",
            narration_text="술집 안에서는 여관주인이 의자를 정리하며 하루를 마무리하고 있었다.",
            observer_narration_text="술집에서는 여관주인이 의자를 정리하며 하루를 마무리하고 있었다.",
            probability=0.4,
            cooldown_tick=1,
            rumor_base_score=1,
        ),
    ]
