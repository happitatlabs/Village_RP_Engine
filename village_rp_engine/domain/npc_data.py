from __future__ import annotations

from village_rp_engine.models.npc import NPC


def build_npcs() -> list[NPC]:
    return [
        NPC(npc_id="blacksmith", name="대장장이", role="blacksmith", influence="medium", influence_score=0),
        NPC(npc_id="farmer", name="농부", role="farmer", influence="low", influence_score=0),
        NPC(npc_id="innkeeper", name="여관주인", role="innkeeper", influence="medium", influence_score=0),
        NPC(npc_id="village_elder", name="촌장", role="leader", influence="high", influence_score=1),
        NPC(npc_id="guard_captain", name="경비대장", role="guard", influence="high", influence_score=1),
        NPC(npc_id="ethan", name="에단", role="village_youth", influence="medium", influence_score=1),
    ]
