import json
from datetime import date

import pytest

from downloads.__main__ import collect, load_packages, main
from downloads.registries import Counts, FetchError

TODAY = date(2026, 11, 15)

PACKAGES = """\
pypi = ["solvor", "grafeo"]
crates = ["gwp"]
nuget = ["Grafeo"]
docker = ["grafeo/grafeo-server"]
npm = ["gwp-js"]
"""


def fetchers(**overrides):
    """Healthy fetchers for every registry, with per-registry overrides."""
    base = {
        "pypi": lambda name, today: Counts(1000, 100),
        "crates": lambda name, today: Counts(500, 50),
        "docker": lambda name, today: Counts(300, None),
        "nuget": lambda name, today: Counts(200, None),
        "npm": lambda name, today: Counts(100, 10),
    }
    return base | overrides


def failing(name, today):
    raise FetchError("boom")


def test_load_packages_fills_missing_registries(tmp_path):
    path = tmp_path / "packages.toml"
    path.write_text('crates = ["gwp"]\n', encoding="utf-8")
    assert load_packages(path) == {"pypi": [], "crates": ["gwp"], "docker": [], "nuget": [], "npm": []}


def test_load_packages_rejects_unknown_registries(tmp_path):
    path = tmp_path / "packages.toml"
    path.write_text('maven = ["gwp"]\n', encoding="utf-8")
    with pytest.raises(SystemExit, match="maven"):
        load_packages(path)


def test_collect_sums_packages_per_registry_in_fixed_order(tmp_path):
    packages = {"pypi": ["a", "b"], "crates": ["c"], "docker": [], "nuget": [], "npm": ["d"]}
    stats, successes = collect(packages, {}, TODAY, fetchers(), sleep=lambda s: None)
    assert [(s.key, s.total, s.last30) for s in stats] == [
        ("pypi", 2000, 200),
        ("crates", 500, 50),
        ("docker", 0, None),
        ("nuget", 0, None),
        ("npm", 100, 10),
    ]
    assert successes == 4


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
    assert next(s for s in stats if s.key == "docker").total == 0


def test_main_writes_history_and_both_cards(tmp_path, capsys):
    (tmp_path / "packages.toml").write_text(PACKAGES, encoding="utf-8")
    assert main(tmp_path, TODAY, fetchers(), sleep=lambda s: None) == 0
    history = json.loads((tmp_path / "data" / "history.json").read_text(encoding="utf-8"))
    assert history["docker"]["grafeo/grafeo-server"] == [{"date": "2026-11-15", "total": 300, "last30": None}]
    for theme in ("light", "dark"):
        svg = (tmp_path / "assets" / f"downloads-{theme}.svg").read_text(encoding="utf-8")
        assert svg.startswith("<svg")
    assert "PyPI" in capsys.readouterr().out


def test_main_writes_nothing_when_every_fetch_fails(tmp_path, capsys):
    (tmp_path / "packages.toml").write_text(PACKAGES, encoding="utf-8")
    all_failing = {key: failing for key in ("pypi", "crates", "docker", "nuget", "npm")}
    assert main(tmp_path, TODAY, all_failing, sleep=lambda s: None) == 1
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "assets").exists()
    assert "::error::" in capsys.readouterr().out
