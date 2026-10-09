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
from downloads.registries import FETCHERS, LABELS, ORDER, SNAPSHOT_30D, Counts
from downloads.render import VARIANTS, RegistryStat, render_card

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
    """Fetch every package, record fresh snapshots, and return per-registry stats and the number of successes.

    Registries without packages are left out. A number stays None (shown as n/a) when no package has one.
    """
    stats, successes = [], 0
    for registry in ORDER:
        names = packages.get(registry, [])
        if not names:
            continue
        totals, last30s = [], []
        for i, name in enumerate(names):
            if i and registry in PACING:
                sleep(PACING[registry])
            try:
                counts = fetchers[registry](name, today)
            except Exception as error:  # any surprise from one package must not sink the whole run
                previous = latest(history, registry, name)
                fallback = f"using snapshot from {previous['date']}" if previous else "no data yet"
                warn(f"{LABELS[registry]} {name}: {error!r}; {fallback}")
                if previous:
                    totals.append(previous["total"])
                    last30s.append(previous["last30"])
                continue
            successes += 1
            last30 = counts.last30
            if registry in SNAPSHOT_30D:
                last30 = last30_from_snapshots(snapshots(history, registry, name), today, counts.total)
            record(history, registry, name, today, counts.total, last30)
            totals.append(counts.total)
            last30s.append(last30)
        stats.append(RegistryStat(registry, LABELS[registry], _known_sum(totals), _known_sum(last30s)))
    return stats, successes


def _known_sum(values: list[int | None]) -> int | None:
    known = [v for v in values if v is not None]
    return sum(known) if known else None


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
    for suffix, (shown, columns, width) in VARIANTS.items():
        for theme in ("light", "dark"):
            card = render_card(stats, today, theme, shown, columns, width)
            (assets / f"downloads{suffix}-{theme}.svg").write_text(card, encoding="utf-8")
    for s in stats:
        total = "n/a" if s.total is None else f"{s.total:,}"
        recent = "n/a" if s.last30 is None else f"{s.last30:,}"
        print(f"{s.label:<10} {total:>12} all time   {recent:>10} last 30 days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
