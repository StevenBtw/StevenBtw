from datetime import date

from downloads.history import last30_from_snapshots, latest, load, prune, record, save, snapshots

TODAY = date(2026, 11, 15)  # a Sunday; 30 days earlier is 2026-10-16


def snap(day, total, last30=None):
    return {"date": day, "total": total, "last30": last30}


def test_exact_snapshot_30_days_ago():
    found = [snap("2026-10-16", 1000)]
    assert last30_from_snapshots(found, TODAY, 1300) == 300


def test_interpolates_between_weekly_snapshots():
    # 2026-10-11: 1000, 2026-10-18: 1070 -> on 2026-10-16 (5 of 7 days later): 1050
    found = [snap("2026-10-11", 1000), snap("2026-10-18", 1070)]
    assert last30_from_snapshots(found, TODAY, 1500) == 450


def test_not_enough_history_is_unknown():
    found = [snap("2026-10-25", 1000), snap("2026-11-01", 1100)]
    assert last30_from_snapshots(found, TODAY, 1200) is None


def test_no_history_is_unknown():
    assert last30_from_snapshots([], TODAY, 1200) is None


def test_missed_runs_interpolate_up_to_today():
    # Only a snapshot from 44 days ago, then nothing until today: line from (2026-10-02, 0) to (today, 440).
    found = [snap("2026-10-02", 0)]
    assert last30_from_snapshots(found, TODAY, 440) == 300


def test_a_shrinking_total_never_gives_negative_downloads():
    found = [snap("2026-10-16", 1000)]
    assert last30_from_snapshots(found, TODAY, 900) == 0


def test_todays_earlier_snapshot_is_ignored_for_the_estimate():
    found = [snap("2026-10-16", 1000), snap("2026-11-15", 5)]
    assert last30_from_snapshots(found, TODAY, 1300) == 300


def test_record_replaces_a_same_day_snapshot_and_keeps_dates_sorted():
    history = {}
    record(history, "nuget", "Grafeo", date(2026, 11, 8), 900, None)
    record(history, "nuget", "Grafeo", date(2026, 11, 1), 800, None)
    record(history, "nuget", "Grafeo", date(2026, 11, 8), 950, 40)
    assert snapshots(history, "nuget", "Grafeo") == [snap("2026-11-01", 800), snap("2026-11-08", 950, 40)]
    assert latest(history, "nuget", "Grafeo") == snap("2026-11-08", 950, 40)


def test_latest_of_unknown_package_is_none():
    assert latest({}, "nuget", "Grafeo") is None


def test_prune_drops_snapshots_older_than_90_days():
    history = {"docker": {"grafeo/grafeo-server": [snap("2026-08-16", 1), snap("2026-08-17", 2), snap("2026-11-15", 3)]}}
    prune(history, TODAY)
    assert history == {"docker": {"grafeo/grafeo-server": [snap("2026-08-17", 2), snap("2026-11-15", 3)]}}


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "data" / "history.json"
    history = {"npm": {"gwp-js": [snap("2026-11-15", 941, 16)]}}
    save(path, history)
    assert load(path) == history
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_load_missing_file_is_empty(tmp_path):
    assert load(tmp_path / "missing.json") == {}
