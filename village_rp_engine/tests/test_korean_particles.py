from __future__ import annotations

from village_rp_engine.korean import choose_subject_particle, choose_topic_particle, with_particle


def test_particle_helper_handles_subject_particle() -> None:
    assert with_particle("대장장이", "이/가") == "대장장이가"
    assert with_particle("여관주인", "이/가") == "여관주인이"
    assert choose_subject_particle("농부") == "가"
    assert choose_subject_particle("상인") == "이"


def test_particle_helper_handles_topic_particle() -> None:
    assert with_particle("대장장이", "은/는") == "대장장이는"
    assert with_particle("여관주인", "은/는") == "여관주인은"
    assert choose_topic_particle("기사") == "는"
    assert choose_topic_particle("상인") == "은"
