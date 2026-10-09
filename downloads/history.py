"""Per-package snapshots of all-time totals, and the 30-day number derived from them."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

# registry -> package -> snapshots {"date": "YYYY-MM-DD", "total": int, "last30": int | None}, oldest first
History = dict[str, dict[str, list[dict]]]

KEEP_DAYS = 90
WINDOW_DAYS = 30


def load(path: Path) -> History:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, history: History) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def snapshots(history: History, registry: str, name: str) -> list[dict]:
    return history.get(registry, {}).get(name, [])


def latest(history: History, registry: str, name: str) -> dict | None:
    found = snapshots(history, registry, name)
    return found[-1] if found else None


def record(history: History, registry: str, name: str, day: date, total: int, last30: int | None) -> None:
    """Store today's snapshot, replacing an earlier one from the same day (e.g. a manual re-run)."""
    found = history.setdefault(registry, {}).setdefault(name, [])
    found[:] = [s for s in found if s["date"] != day.isoformat()]
    found.append({"date": day.isoformat(), "total": total, "last30": last30})
    found.sort(key=lambda s: s["date"])


def last30_from_snapshots(found: list[dict], today: date, total_now: int) -> int | None:
    """Downloads in the last 30 days: today's total minus the total 30 days ago.

    The total 30 days ago is interpolated linearly between the snapshots on either side of that day,
    with today's total as the newest point. None when no snapshot is at least 30 days old.
    """
    target = today - timedelta(days=WINDOW_DAYS)
    points = [(date.fromisoformat(s["date"]), s["total"]) for s in found if s["date"] < today.isoformat()]
    points.append((today, total_now))
    older = [p for p in points if p[0] <= target]
    if not older:
        return None
    day0, total0 = older[-1]
    day1, total1 = next(p for p in points if p[0] >= target)
    if day1 == day0:
        then = total0
    else:
        then = total0 + (total1 - total0) * (target - day0).days / (day1 - day0).days
    return max(0, round(total_now - then))


def prune(history: History, today: date) -> None:
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    for packages in history.values():
        for name, found in packages.items():
            packages[name] = [s for s in found if s["date"] >= cutoff]
