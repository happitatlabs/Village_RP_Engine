from __future__ import annotations


def with_particle(word: str, pair: str) -> str:
    first, second = pair.split("/")
    return f"{word}{choose_particle(word, first, second)}"


def choose_subject_particle(word: str) -> str:
    return choose_particle(word, "이", "가")


def choose_topic_particle(word: str) -> str:
    return choose_particle(word, "은", "는")


def choose_particle(word: str, consonant_particle: str, vowel_particle: str) -> str:
    if not word:
        return vowel_particle

    last_char = word[-1]
    code = ord(last_char)
    if 0xAC00 <= code <= 0xD7A3:
        has_final_consonant = (code - 0xAC00) % 28 != 0
        return consonant_particle if has_final_consonant else vowel_particle

    return vowel_particle
