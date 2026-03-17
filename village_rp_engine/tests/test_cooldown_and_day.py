from __future__ import annotations

from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules
from village_rp_engine.models.event import EventDefinition, TriggeredEvent
from village_rp_engine.systems.rumor_system import RumorSystem


def build_engine(event_definitions: list[EventDefinition] | None = None) -> TickEngine:
    return TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=event_definitions or build_event_definitions(),
        seed=1,
    )


def test_event_cooldown_blocks_repeated_trigger() -> None:
    event_definitions = [
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
            cooldown_tick=10,
            rumor_base_score=2,
        )
    ]
    engine = build_engine(event_definitions)
    state = create_initial_world_state(player_location="광장")

    for _ in range(2):
        state = engine.run_tick(state)
    assert [event.event_id for event in state.triggered_events] == ["argument_at_tavern"]

    for _ in range(5):
        state = engine.run_tick(state)

    assert state.tick == 7
    assert state.time_phase == "저녁"
    assert state.triggered_events == []
    assert state.event_last_trigger_tick["argument_at_tavern"] == 2


def test_rumor_dedupe_prevents_same_day_duplicates() -> None:
    rumor_system = RumorSystem(npcs=build_npcs())
    state = create_initial_world_state(player_location="광장")
    state.tick = 2
    state.day = 1
    hidden_event = TriggeredEvent(
        event_id="argument_at_tavern",
        time_phase="저녁",
        location="술집",
        actor_ids=("blacksmith", "farmer"),
        outcome_text="대장장이와 농부가 술집에서 말다툼을 벌였다.",
        rumor_text="술집에서 대장장이와 농부가 언성을 높였다는 소문이 퍼졌다.",
        narration_text="네가 술집에 들어섰을 때, 대장장이와 농부가 날카롭게 언성을 높이고 있었다.",
        observer_narration_text="술집에서 대장장이와 농부가 날카롭게 언성을 높이고 있었다.",
        rumor_base_score=2,
        witnessed=False,
    )

    first_rumors = rumor_system.create_rumors(state, [hidden_event])
    second_rumors = rumor_system.create_rumors(state, [hidden_event])
    state.rumor_log.extend(first_rumors)
    state.rumor_log.extend(second_rumors)

    assert len(first_rumors) == 1
    assert second_rumors == []
    assert len(state.rumor_log) == 1
    assert state.rumor_history_keys == {"argument_at_tavern:1"}


def test_day_increments_on_dawn_to_morning_transition() -> None:
    engine = build_engine()
    state = create_initial_world_state()

    for _ in range(4):
        state = engine.run_tick(state)

    assert state.day == 1
    assert state.time_phase == "새벽"

    state = engine.run_tick(state)

    assert state.day == 2
    assert state.time_phase == "아침"


def test_argument_at_tavern_creates_rumor() -> None:
    rumor_system = RumorSystem(npcs=build_npcs())
    state = create_initial_world_state(player_location="광장")
    state.tick = 2
    state.day = 1
    hidden_event = TriggeredEvent(
        event_id="argument_at_tavern",
        time_phase="저녁",
        location="술집",
        actor_ids=("blacksmith", "farmer"),
        outcome_text="대장장이와 농부가 술집에서 말다툼을 벌였다.",
        rumor_text="술집에서 대장장이와 농부가 언성을 높였다는 소문이 퍼졌다.",
        narration_text="네가 술집에 들어섰을 때, 대장장이와 농부가 날카롭게 언성을 높이고 있었다.",
        observer_narration_text="술집에서 대장장이와 농부가 날카롭게 언성을 높이고 있었다.",
        rumor_base_score=2,
        witnessed=False,
    )

    rumors = rumor_system.create_rumors(state, [hidden_event])

    assert len(rumors) == 1
    assert "소문 판정: argument_at_tavern base=2 influence=0 total=2 -> 생성" in state.world_log


def test_influential_actor_allows_low_base_event_to_become_rumor() -> None:
    rumor_system = RumorSystem(npcs=build_npcs())
    state = create_initial_world_state(player_location="술집")
    state.tick = 2
    state.day = 1
    hidden_event = TriggeredEvent(
        event_id="elder_guard_discussion",
        time_phase="저녁",
        location="술집",
        actor_ids=("village_elder", "guard_captain"),
        outcome_text="촌장과 경비대장이 술집 구석에서 조용히 이야기를 나눴다.",
        rumor_text="촌장과 경비대장이 무언가를 의논했다는 말이 돌았다.",
        narration_text="",
        observer_narration_text="",
        rumor_base_score=1,
        witnessed=False,
    )

    rumors = rumor_system.create_rumors(state, [hidden_event])

    assert len(rumors) == 1
    assert rumors[0].source_event_id == "elder_guard_discussion"


def test_rumor_score_uses_max_actor_influence() -> None:
    rumor_system = RumorSystem(npcs=build_npcs())
    state = create_initial_world_state(player_location="술집")
    state.tick = 2
    state.day = 1
    hidden_event = TriggeredEvent(
        event_id="elder_farmer_discussion",
        time_phase="저녁",
        location="술집",
        actor_ids=("village_elder", "farmer", "guard_captain"),
        outcome_text="촌장과 농부, 경비대장이 함께 이야기를 나눴다.",
        rumor_text="영향력 있는 인물들이 무언가를 논의했다는 말이 돌았다.",
        narration_text="",
        observer_narration_text="",
        rumor_base_score=1,
        witnessed=False,
    )

    rumors = rumor_system.create_rumors(state, [hidden_event])

    assert len(rumors) == 1
    assert "소문 판정: elder_farmer_discussion base=1 influence=1 total=2 -> 생성" in state.world_log
