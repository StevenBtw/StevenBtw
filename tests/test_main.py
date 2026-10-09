import json
from datetime import date

import pytest

from downloads.__main__ import collect, load_packages, main
from downloads.registries import Counts, FetchError, fetch_pypi

TODAY = date(2026, 11, 15)

PACKAGES = """\
pypi = ["solvor", "grafeo"]
crates = ["gwp"]
nuget = ["Grafeo"]
docker = ["grafeo/grafeo-server"]
npm = ["gwp-js"]
github = ["GrafeoDB/grafeo"]
pubdev = ["grafeo"]
"""


def fetchers(**overrides):
    """Healthy fetchers for every registry, with per-registry overrides."""
    base = {
        "pypi": lambda name, today: Counts(1000, 100),
        "crates": lambda name, today: Counts(500, 50),
        "docker": lambda name, today: Counts(300, None),
        "nuget": lambda name, today: Counts(200, None),
        "npm": lambda name, today: Counts(100, 10),
        "github": lambda name, today: Counts(80, None),
        "pubdev": lambda name, today: Counts(None, 40),
    }
    return base | overrides


def failing(name, today):
    raise FetchError("boom")


def test_load_packages_fills_missing_registries(tmp_path):
    path = tmp_path / "packages.toml"
    path.write_text('crates = ["gwp"]\n', encoding="utf-8")
    assert load_packages(path) == {
        "pypi": [], "crates": ["gwp"], "docker": [], "nuget": [], "npm": [], "github": [], "pubdev": []
    }


def test_load_packages_rejects_unknown_registries(tmp_path):
    path = tmp_path / "packages.toml"
    path.write_text('maven = ["gwp"]\n', encoding="utf-8")
    with pytest.raises(SystemExit, match="maven"):
        load_packages(path)


def test_collect_sums_packages_per_registry_and_skips_registries_without_packages():
    packages = {"pypi": ["a", "b"], "crates": ["c"], "docker": [], "nuget": [], "npm": ["d"]}
    stats, successes = collect(packages, {}, TODAY, fetchers(), sleep=lambda s: None)
    assert [(s.key, s.total, s.last30) for s in stats] == [("pypi", 2000, 200), ("crates", 500, 50), ("npm", 100, 10)]
    assert successes == 4


def test_a_registry_without_all_time_numbers_stays_unknown():
    stats, _ = collect({"pubdev": ["grafeo"]}, {}, TODAY, fetchers(), sleep=lambda s: None)
    assert [(s.key, s.label, s.total, s.last30) for s in stats] == [("pubdev", "pub.dev", None, 40)]


def test_failed_package_with_unknown_total_falls_back_to_unknown(capsys):
    history = {"pubdev": {"grafeo": [{"date": "2026-11-08", "total": None, "last30": 30}]}}
    stats, _ = collect({"pubdev": ["grafeo"]}, history, TODAY, fetchers(pubdev=failing), sleep=lambda s: None)
    assert [(s.total, s.last30) for s in stats] == [(None, 30)]


def test_github_releases_get_30_days_from_history():
    history = {"github": {"GrafeoDB/grafeo": [{"date": "2026-10-16", "total": 20, "last30": None}]}}
    stats, _ = collect({"github": ["GrafeoDB/grafeo"]}, history, TODAY, fetchers(), sleep=lambda s: None)
    assert [(s.key, s.total, s.last30) for s in stats] == [("github", 80, 60)]


def test_collect_paces_pypi_requests():
    pauses = []
    packages = {"pypi": ["a", "b", "c"], "crates": [], "docker": [], "nuget": [], "npm": []}
    collect(packages, {}, TODAY, fetchers(), sleep=pauses.append)
    assert pauses == [13.0, 13.0]


def test_snapshot_registries_get_30_days_from_history():
    history = {"nuget": {"Grafeo": [{"date": "2026-10-16", "total": 150, "last30": None}]}}
    packages = {"pypi": [], "crates": [], "docker": [], "nuget": ["Grafeo"], "npm": []}
    stats, _ = collect(packages, history, TODAY, fetchers(), sleep=lambda s: None)
    nuget = next(s for s in stats if s.key == "nuget")
    assert (nuget.total, nuget.last30) == (200, 50)
    assert history["nuget"]["Grafeo"][-1] == {"date": "2026-11-15", "total": 200, "last30": 50}


def test_failed_package_falls_back_to_its_last_snapshot_and_records_nothing(capsys):
    history = {"crates": {"gwp": [{"date": "2026-11-08", "total": 480, "last30": 45}]}}
    packages = {"pypi": [], "crates": ["gwp"], "docker": [], "nuget": [], "npm": []}
    stats, successes = collect(packages, history, TODAY, fetchers(crates=failing), sleep=lambda s: None)
    crates = next(s for s in stats if s.key == "crates")
    assert (crates.total, crates.last30) == (480, 45)
    assert successes == 0
    assert history["crates"]["gwp"] == [{"date": "2026-11-08", "total": 480, "last30": 45}]
    assert "::warning::crates.io gwp" in capsys.readouterr().out


def test_unknown_package_counts_zero_and_others_still_count(capsys):
    def crates(name, today):
        if name == "typo":
            raise FetchError("HTTP 404")
        return Counts(500, 50)

    packages = {"pypi": [], "crates": ["typo", "gwp"], "docker": [], "nuget": [], "npm": []}
    stats, successes = collect(packages, {}, TODAY, fetchers(crates=crates), sleep=lambda s: None)
    crates_stat = next(s for s in stats if s.key == "crates")
    assert (crates_stat.total, crates_stat.last30) == (500, 50)
    assert successes == 1
    assert "crates.io typo" in capsys.readouterr().out


def test_unexpected_json_shape_is_a_failed_fetch_not_a_crash():
    def renamed_field(name, today):
        return {"downloads": 1}["total"]  # KeyError, as if a registry renamed a field

    packages = {"pypi": [], "crates": [], "docker": ["grafeo/grafeo-server"], "nuget": [], "npm": []}
    stats, successes = collect(packages, {}, TODAY, fetchers(docker=renamed_field), sleep=lambda s: None)
    assert successes == 0
    assert next(s for s in stats if s.key == "docker").total is None  # nothing known yet: shown as n/a


def test_reshaped_response_through_a_real_fetcher_falls_back_to_the_last_snapshot(monkeypatch, capsys):
    monkeypatch.setenv("PEPY_API_KEY", "test-key")
    reshaped = {"total_downloads": 999, "downloads": [["2026-11-14", 5]]}  # a list where pepy documents a dict

    def pypi(name, today):
        return fetch_pypi(name, today, get=lambda url, headers=None: reshaped)

    history = {"pypi": {"solvor": [{"date": "2026-11-08", "total": 700, "last30": 70}]}}
    packages = {"pypi": ["solvor"], "crates": [], "docker": [], "nuget": [], "npm": []}
    stats, successes = collect(packages, history, TODAY, fetchers(pypi=pypi), sleep=lambda s: None)
    pypi_stat = next(s for s in stats if s.key == "pypi")
    assert (pypi_stat.total, pypi_stat.last30) == (700, 70)
    assert successes == 0
    assert history["pypi"]["solvor"] == [{"date": "2026-11-08", "total": 700, "last30": 70}]
    assert "::warning::PyPI solvor" in capsys.readouterr().out


def test_main_writes_history_and_the_wide_and_compact_cards(tmp_path, capsys):
    (tmp_path / "packages.toml").write_text(PACKAGES, encoding="utf-8")
    assert main(tmp_path, TODAY, fetchers(), sleep=lambda s: None) == 0
    history = json.loads((tmp_path / "data" / "history.json").read_text(encoding="utf-8"))
    assert history["docker"]["grafeo/grafeo-server"] == [{"date": "2026-11-15", "total": 300, "last30": None}]
    assert history["pubdev"]["grafeo"] == [{"date": "2026-11-15", "total": None, "last30": 40}]
    for variant in ("", "-md", "-sm", "-xs"):
        for theme in ("light", "dark"):
            svg = (tmp_path / "assets" / f"downloads{variant}-{theme}.svg").read_text(encoding="utf-8")
            assert svg.startswith("<svg")
    out = capsys.readouterr().out
    assert "PyPI" in out and "pub.dev" in out


def test_main_writes_nothing_when_every_fetch_fails(tmp_path, capsys):
    (tmp_path / "packages.toml").write_text(PACKAGES, encoding="utf-8")
    all_failing = {key: failing for key in ("pypi", "crates", "docker", "nuget", "npm")}
    assert main(tmp_path, TODAY, all_failing, sleep=lambda s: None) == 1
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "assets").exists()
    assert "::error::" in capsys.readouterr().out
