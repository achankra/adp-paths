"""Seeded refactor target for the /iterative-refactor demo.

This module intentionally ships with lint defects that the L01 gate
catches on attempt 1 and the L03 agent fixes (Ruff --fix in simulate
mode, Claude in live mode) before the gate passes on attempt 2.

Seeded defects (all auto-fixable, so the demo is deterministic):
    - unused imports (F401)
    - unsorted import block (I001)

Do not "clean up" this file — its defects ARE the demo. If you fix
them here, the feedback loop demo passes on the first attempt and
demonstrates nothing. Restore with: git checkout -- sample/
"""

import os
import json
import sys


def summarize_order(order: dict) -> dict:
    """Return a compact summary of an order payload."""
    items = order.get("items", [])
    total = sum(i.get("price", 0) * i.get("quantity", 1) for i in items)
    return {
        "order_id": order.get("id", "unknown"),
        "item_count": len(items),
        "total": round(total, 2),
    }


def is_priority(order: dict) -> bool:
    """Priority orders ship same-day."""
    return order.get("total", 0) >= 500 or order.get("tier") == "gold"
