"""Registry parsing against trimmed live responses (fetched 2026-10-09), and the HTTP retry rules."""

import io
import urllib.error
from datetime import date

import pytest

from downloads.registries import (
    Counts,
    FetchError,
    fetch_crates,
    fetch_docker,
    fetch_npm,
    fetch_nuget,
    fetch_pypi,
    get_json,
    last30_window,
)

TODAY = date(2026, 10, 9)  # window: 2026-09-09 .. 2026-10-08


def fake_get(responses):
    """A stand-in for get_json that serves canned responses by URL and records the calls."""
    calls = []

    def get(url, headers=None):
        calls.append((url, headers))
        if url not in responses:
            raise AssertionError(f"unexpected request: {url}")
        return responses[url]

    get.calls = calls
    return get


def test_last30_window_is_30_days_ending_yesterday():
    assert last30_window(TODAY) == (date(2026, 9, 9), date(2026, 10, 8))


def test_pypi_sums_all_versions_inside_the_window(monkeypatch):
    monkeypatch.setenv("PEPY_API_KEY", "test-key")
    get = fake_get(
        {
            "https://api.pepy.tech/api/v2/projects/solvor": {
                "id": "solvor",
                "total_downloads": 5120,
                "versions": ["0.4.0", "0.5.0"],
                "downloads": {
                    "2026-09-08": {"0.4.0": 7},
                    "2026-09-09": {"0.4.0": 3, "0.5.0": 10},
                    "2026-10-08": {"0.5.0": 20},
                    "2026-10-09": {"0.5.0": 50},
                },
            }
        }
    )
    assert fetch_pypi("solvor", TODAY, get) == Counts(5120, 33)
    assert get.calls[0][1] == {"X-API-Key": "test-key"}


def test_pypi_without_api_key_fails(monkeypatch):
    monkeypatch.delenv("PEPY_API_KEY", raising=False)
    with pytest.raises(FetchError, match="PEPY_API_KEY"):
        fetch_pypi("solvor", TODAY, fake_get({}))


def test_crates_adds_extra_downloads_inside_the_window():
    get = fake_get(
        {
            "https://crates.io/api/v1/crates/gwp": {"crate": {"name": "gwp", "downloads": 1581, "recent_downloads": 410}},
            "https://crates.io/api/v1/crates/gwp/downloads": {
                "version_downloads": [
                    {"version": 2242023, "downloads": 4, "date": "2026-09-08"},
                    {"version": 2242023, "downloads": 2, "date": "2026-09-09"},
                    {"version": 2242023, "downloads": 5, "date": "2026-10-08"},
                    {"version": 2242023, "downloads": 9, "date": "2026-10-09"},
                ],
                "meta": {
                    "extra_downloads": [
                        {"date": "2026-09-01", "downloads": 8},
                        {"date": "2026-09-20", "downloads": 1},
                    ]
                },
            },
        }
    )
    assert fetch_crates("gwp", TODAY, get) == Counts(1581, 8)


def test_npm_sums_yearly_windows_from_creation_date():
    get = fake_get(
        {
            "https://registry.npmjs.org/@grafeo-db/js": {"name": "@grafeo-db/js", "time": {"created": "2024-03-01T10:57:51.698Z"}},
            "https://api.npmjs.org/downloads/point/2024-03-01:2025-02-28/@grafeo-db/js": {"downloads": 100},
            "https://api.npmjs.org/downloads/point/2025-03-01:2026-02-28/@grafeo-db/js": {"downloads": 200},
            "https://api.npmjs.org/downloads/point/2026-03-01:2026-10-09/@grafeo-db/js": {"downloads": 300},
            "https://api.npmjs.org/downloads/point/last-month/@grafeo-db/js": {
                "downloads": 16,
                "start": "2026-09-08",
                "end": "2026-10-07",
                "package": "@grafeo-db/js",
            },
        }
    )
    assert fetch_npm("@grafeo-db/js", TODAY, get) == Counts(600, 16)


def test_npm_package_created_today_still_counts_today():
    get = fake_get(
        {
            "https://registry.npmjs.org/gwp-js": {"time": {"created": "2026-10-09T08:00:00.000Z"}},
            "https://api.npmjs.org/downloads/point/2026-10-09:2026-10-09/gwp-js": {"downloads": 0},
            "https://api.npmjs.org/downloads/point/last-month/gwp-js": {"downloads": 0},
        }
    )
    assert fetch_npm("gwp-js", TODAY, get) == Counts(0, 0)


def test_nuget_matches_package_id_case_insensitively():
    get = fake_get(
        {
            "https://azuresearch-usnc.nuget.org/query?q=packageid:Grafeo&prerelease=true": {
                "totalHits": 1,
                "data": [{"id": "Grafeo", "version": "0.5.44", "totalDownloads": 2776}],
            }
        }
    )
    assert fetch_nuget("Grafeo", TODAY, get) == Counts(2776, None)


def test_nuget_unknown_package_fails():
    get = fake_get({"https://azuresearch-usnc.nuget.org/query?q=packageid:Nope&prerelease=true": {"totalHits": 0, "data": []}})
    with pytest.raises(FetchError, match="Nope"):
        fetch_nuget("Nope", TODAY, get)


def test_docker_reads_pull_count():
    get = fake_get(
        {
            "https://hub.docker.com/v2/repositories/grafeo/grafeo-server/": {
                "namespace": "grafeo",
                "name": "grafeo-server",
                "pull_count": 8038,
            }
        }
    )
    assert fetch_docker("grafeo/grafeo-server", TODAY, get) == Counts(8038, None)


def http_error(code, headers=None):
    return urllib.error.HTTPError("https://example.test", code, "error", headers or {}, None)


def scripted_opener(*outcomes):
    """An opener that raises or returns the given outcomes in order."""
    remaining = list(outcomes)

    def opener(request, timeout):
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return io.BytesIO(outcome)

    return opener


def test_get_json_returns_parsed_body():
    assert get_json("https://example.test", opener=scripted_opener(b'{"a": 1}'), sleep=lambda s: None) == {"a": 1}


def test_get_json_retries_once_after_a_short_pause():
    pauses = []
    opener = scripted_opener(urllib.error.URLError("reset"), b'{"ok": true}')
    assert get_json("https://example.test", opener=opener, sleep=pauses.append) == {"ok": True}
    assert pauses == [5.0]


def test_get_json_waits_as_long_as_a_429_asks():
    pauses = []
    opener = scripted_opener(http_error(429, {"X-Rate-Limit-Retry-After-Seconds": "12"}), b"{}")
    get_json("https://example.test", opener=opener, sleep=pauses.append)
    assert pauses == [12.0]


def test_get_json_caps_a_429_wait_at_60_seconds():
    pauses = []
    opener = scripted_opener(http_error(429, {"Retry-After": "600"}), b"{}")
    get_json("https://example.test", opener=opener, sleep=pauses.append)
    assert pauses == [60.0]


def test_get_json_gives_up_after_the_retry():
    opener = scripted_opener(http_error(500), http_error(500))
    with pytest.raises(FetchError, match="500"):
        get_json("https://example.test", opener=opener, sleep=lambda s: None)


def test_get_json_treats_invalid_json_as_a_failure():
    opener = scripted_opener(b"<html>", b"<html>")
    with pytest.raises(FetchError):
        get_json("https://example.test", opener=opener, sleep=lambda s: None)


def test_get_json_sends_a_user_agent():
    seen = []

    def opener(request, timeout):
        seen.append(request.get_header("User-agent"))
        return io.BytesIO(b"{}")

    get_json("https://example.test", opener=opener, sleep=lambda s: None)
    assert seen[0].startswith("StevenBtw-profile-downloads")
