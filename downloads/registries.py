"""Fetch all-time and last-30-day download counts from each package registry."""

from __future__ import annotations

import http.client
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

USER_AGENT = "StevenBtw-profile-downloads (+https://github.com/StevenBtw/StevenBtw)"

# Fetch order. The card sorts registries by downloads; this order only breaks ties.
ORDER =("pypi", "crates", "docker", "nuget", "npm")
LABELS = {"pypi": "PyPI", "crates": "crates.io", "docker": "Docker", "nuget": "NuGet", "npm": "npm"}

# Registries that only publish an all-time total; their 30-day number comes from history snapshots.
SNAPSHOT_30D = frozenset({"docker", "nuget"})

NPM_DATA_START = date(2015, 1, 10)  # npm download statistics begin on this day
NPM_WINDOW = timedelta(days=365)  # npm accepts ranges of up to 18 months per request

GetJson = Callable[..., dict]


class FetchError(Exception):
    """A registry request failed or the registry does not know the package."""


@dataclass(frozen=True)
class Counts:
    total: int
    last30: int | None  # None when the registry has no 30-day number


def get_json(
    url: str,
    headers: dict[str, str] | None = None,
    *,
    opener: Callable = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """GET a JSON document, retrying once. On HTTP 429 the retry waits as long as the server asks (max 60 s)."""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}
    )
    error: Exception | None = None
    for attempt in range(2):
        if attempt:
            sleep(_retry_wait(error))
        try:
            with opener(request, timeout=30) as response:
                return json.load(response)
        # urllib wraps only send errors in URLError; a dropped or truncated response arrives as a raw
        # OSError or HTTPException. URLError and TimeoutError are OSErrors too.
        except (OSError, http.client.HTTPException, ValueError) as caught:
            error = caught
    raise FetchError(f"{url}: {error}") from error


def _retry_wait(error: Exception | None) -> float:
    if isinstance(error, urllib.error.HTTPError) and error.code == 429:
        header = error.headers.get("X-Rate-Limit-Retry-After-Seconds") or error.headers.get("Retry-After")
        try:
            return min(float(header), 60.0)
        except (TypeError, ValueError):
            return 60.0
    return 5.0


def last30_window(today: date) -> tuple[date, date]:
    """The 30 days ending yesterday, both ends inclusive, so a partial day is never counted."""
    return today - timedelta(days=30), today - timedelta(days=1)


def fetch_pypi(name: str, today: date, get: GetJson = get_json) -> Counts:
    key = os.environ.get("PEPY_API_KEY")
    if not key:
        raise FetchError("PEPY_API_KEY is not set")
    data = get(f"https://api.pepy.tech/api/v2/projects/{name}", {"X-API-Key": key})
    start, end = last30_window(today)
    last30 = sum(
        count
        for day, versions in data["downloads"].items()
        if start <= date.fromisoformat(day) <= end
        for count in versions.values()
    )
    return Counts(int(data["total_downloads"]), last30)


def fetch_crates(name: str, today: date, get: GetJson = get_json) -> Counts:
    total = get(f"https://crates.io/api/v1/crates/{name}")["crate"]["downloads"]
    daily = get(f"https://crates.io/api/v1/crates/{name}/downloads")
    start, end = last30_window(today)
    rows = daily["version_downloads"] + daily["meta"]["extra_downloads"]
    last30 = sum(row["downloads"] for row in rows if start <= date.fromisoformat(row["date"]) <= end)
    return Counts(int(total), last30)


def fetch_npm(name: str, today: date, get: GetJson = get_json) -> Counts:
    created = date.fromisoformat(get(f"https://registry.npmjs.org/{name}")["time"]["created"][:10])
    total = 0
    start = max(created, NPM_DATA_START)
    while start <= today:
        end = min(start + NPM_WINDOW - timedelta(days=1), today)
        total += get(f"https://api.npmjs.org/downloads/point/{start}:{end}/{name}")["downloads"]
        start = end + timedelta(days=1)
    last30 = get(f"https://api.npmjs.org/downloads/point/last-month/{name}")["downloads"]
    return Counts(total, int(last30))


def fetch_nuget(name: str, today: date, get: GetJson = get_json) -> Counts:
    data = get(f"https://azuresearch-usnc.nuget.org/query?q=packageid:{name}&prerelease=true")
    for package in data["data"]:
        if package["id"].lower() == name.lower():
            return Counts(int(package["totalDownloads"]), None)
    raise FetchError(f"NuGet does not know package {name}")


def fetch_docker(name: str, today: date, get: GetJson = get_json) -> Counts:
    data = get(f"https://hub.docker.com/v2/repositories/{name}/")
    return Counts(int(data["pull_count"]), None)


FETCHERS: dict[str, Callable[[str, date], Counts]] = {
    "pypi": fetch_pypi,
    "crates": fetch_crates,
    "docker": fetch_docker,
    "nuget": fetch_nuget,
    "npm": fetch_npm,
}
