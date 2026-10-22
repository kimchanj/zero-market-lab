"""Human Design Quarter reference metadata, separate from solar calculations."""

from __future__ import annotations

import json
from pathlib import Path

from zero_market_lab.transit.calendar import GATE_SEQUENCE


def load_quarters(root: Path) -> tuple[list[dict], dict[int, dict]]:
    document = json.loads((root / "data/reference/human_design_quarters.json").read_text(encoding="utf-8"))
    quarters = document["quarters"]
    if len(quarters) != 4 or {item["id"] for item in quarters} != {
        "initiation", "civilization", "duality", "mutation"
    }:
        raise ValueError("Exactly four distinct Human Design Quarters are required")
    positions = {gate: index for index, gate in enumerate(GATE_SEQUENCE)}
    gate_map: dict[int, dict] = {}
    for item in quarters:
        start = positions[item["start_gate"]]
        gates = [GATE_SEQUENCE[(start + offset) % 64] for offset in range(16)]
        if gates[-1] != item["end_gate"] or item["turning_gate"] not in gates:
            raise ValueError(f"Invalid Quarter boundaries: {item['id']}")
        if any(gate in gate_map for gate in gates):
            raise ValueError("Quarter Gate overlap")
        if not all(item[field] for field in ("name", "name_ko", "theme", "theme_ko")):
            raise ValueError("Quarter names and themes are required")
        gate_map.update({gate: item for gate in gates})
    if set(gate_map) != set(range(1, 65)):
        raise ValueError("Quarter Gates must cover 1–64 exactly once")
    return quarters, gate_map
