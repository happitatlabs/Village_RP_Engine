from __future__ import annotations

from village_rp_engine.config import DEFAULT_HOME_LOCATION, PUBLIC_LOCATIONS


def build_locations() -> list[str]:
    return [*PUBLIC_LOCATIONS, DEFAULT_HOME_LOCATION]
