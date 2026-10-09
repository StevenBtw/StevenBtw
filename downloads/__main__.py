"""Fetch download counts, update the history and write the light and dark cards.

Run from the repository root: uv run python -m downloads
"""

from __future__ import annotations

import sys
import time
import tomllib
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from downloads.history import History, last30_from_snapshots, latest, load, prune, record, save, snapshots
from downloads.registries import FETCHERS, LABELS, ORDER, SNAPSHOT_30D, Counts, FetchError
from downloads.render import RegistryStat, render_card

ROOT = Path(__file__).resolve().parent.parent

# Seconds to wait between two packages of the same registry, to stay inside rate limits.
PACING = {"pypi": 13.0, "crates": 2.0}

Fetcher = Callable[[str, date], Counts]


def warn(message: str) -> None:
    print(f"::warning::{message}", flush=True)


def load_packages(path: Path) -> dict[str, list[str]]:
    with path.open("rb") as file:
        config = tomllib.load(file)
    unknown = sorted(set(config) - set(ORDER))
    if unknown:
        raise SystemExit(f"Unknown registries in {path.name}: {', '.join(unknown)}")
    return {registry: list(config.get(registry, [])) for registry in ORDER}


def collect(
    packages: dict[str, list[str]],
    history: History,
    today: date,
    fetchers: dict[str, Fetcher] = FETCHERS,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[RegistryStat], int]:
    """Fetch every package, record fresh snapshots, and return per-registry stats and the number of successes."""
    stats, successes = [], 0
    for registry in ORDER:
        total, last30_parts = 0, []
        for i, name in enumerate(packages[registry]):
            if i and registry in PACING:
                sleep(PACING[registry])
            try:
                counts = fetchers[registry](name, today)
            except (FetchError, KeyError, TypeError, ValueError) as error:
                previous = latest(history, registry, name)
                fallback = f"using snapshot from {previous['date']}" if previous else "counting 0"
                warn(f"{LABELS[registry]} {name}: {error!r}; {fallback}")
                if previous:
                    total += previous["total"]
                    if previous["last30"] is not None:
                        last30_parts.append(previous["last30"])
                continue
            successes += 1
            last30 = counts.last30
            if registry in SNAPSHOT_30D:
                last30 = last30_from_snapshots(snapshots(history, registry, name), today, counts.total)
            record(history, registry, name, today, counts.total, last30)
            total += counts.total
            if last30 is not None:
                last30_parts.append(last30)
        stats.append(RegistryStat(registry, LABELS[registry], total, sum(last30_parts) if last30_parts else None))
    return stats, successes


def main(
    root: Path = ROOT,
    today: date | None = None,
    fetchers: dict[str, Fetcher] = FETCHERS,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    today = today or datetime.now(UTC).date()
    packages = load_packages(root / "packages.toml")
    history_path = root / "data" / "history.json"
    history = load(history_path)
    stats, successes = collect(packages, history, today, fetchers, sleep)
    if not successes:
        print("::error::Every package fetch failed; nothing was written.", flush=True)
        return 1
    prune(history, today)
    save(history_path, history)
    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    for theme in ("light", "dark"):
        (assets / f"downloads-{theme}.svg").write_text(render_card(stats, today, theme), encoding="utf-8")
    for s in stats:
        recent = "n/a" if s.last30 is None else f"{s.last30:,}"
        print(f"{s.label:<10} {s.total:>12,} all time   {recent:>10} last 30 days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
