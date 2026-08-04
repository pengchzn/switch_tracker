import sqlite3

import pytest

from tracker_db import connect, init_database, save_play_data


def sample_payload(minutes=45, total_minutes=120):
    return {
        "playHistories": [
            {
                "titleId": "0100TEST",
                "titleName": "Test Game",
                "imageUrl": "https://example.com/game.png",
                "deviceType": "NX",
                "firstPlayedAt": "2025-01-01T00:00:00Z",
                "lastPlayedAt": "2025-01-02T00:00:00Z",
                "totalPlayedDays": 2,
                "totalPlayedMinutes": total_minutes,
            }
        ],
        "recentPlayHistories": [
            {
                "playedDate": "2025-01-02",
                "dailyPlayHistories": [
                    {
                        "titleId": "0100TEST",
                        "titleName": "Test Game",
                        "totalPlayedMinutes": minutes,
                    }
                ],
            }
        ],
    }


def test_repeated_collection_updates_daily_snapshot_without_duplication(tmp_path):
    db_file = tmp_path / "tracker.db"
    save_play_data(sample_payload(minutes=45), "2025-01-02T10:00:00+00:00", db_file)
    save_play_data(sample_payload(minutes=60), "2025-01-02T11:00:00+00:00", db_file)

    with connect(db_file) as connection:
        rows = connection.execute(
            "SELECT played_minutes, collected_at FROM daily_play"
        ).fetchall()

    assert len(rows) == 1
    assert rows[0]["played_minutes"] == 60
    assert rows[0]["collected_at"] == "2025-01-02T11:00:00+00:00"


def test_game_refresh_preserves_translation(tmp_path):
    db_file = tmp_path / "tracker.db"
    save_play_data(sample_payload(), "2025-01-02T10:00:00+00:00", db_file)
    with connect(db_file) as connection:
        connection.execute(
            "UPDATE games SET chinese_name = ? WHERE title_id = ?",
            ("测试游戏", "0100TEST"),
        )

    save_play_data(sample_payload(total_minutes=180), "2025-01-03T10:00:00+00:00", db_file)

    with connect(db_file) as connection:
        row = connection.execute(
            "SELECT chinese_name FROM games WHERE title_id = ?", ("0100TEST",)
        ).fetchone()
    assert row["chinese_name"] == "测试游戏"


def test_migration_deduplicates_legacy_daily_rows(tmp_path):
    db_file = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_file)
    connection.executescript(
        """
        CREATE TABLE games (
            title_id TEXT PRIMARY KEY,
            title_name TEXT NOT NULL,
            image_url TEXT,
            device_type TEXT,
            chinese_name TEXT
        );
        CREATE TABLE daily_play (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_id TEXT NOT NULL,
            played_date TEXT NOT NULL,
            played_minutes INTEGER NOT NULL,
            collected_at TEXT NOT NULL
        );
        INSERT INTO games (title_id, title_name) VALUES ('0100TEST', 'Test Game');
        INSERT INTO daily_play (title_id, played_date, played_minutes, collected_at)
            VALUES ('0100TEST', '2025-01-02', 30, '2025-01-02T10:00:00');
        INSERT INTO daily_play (title_id, played_date, played_minutes, collected_at)
            VALUES ('0100TEST', '2025-01-02', 55, '2025-01-02T11:00:00');
        """
    )
    connection.commit()
    connection.close()

    init_database(db_file)

    with connect(db_file) as migrated:
        rows = migrated.execute("SELECT played_minutes FROM daily_play").fetchall()
    assert [row["played_minutes"] for row in rows] == [55]


def test_daily_snapshot_can_be_corrected_to_zero(tmp_path):
    db_file = tmp_path / "zero.db"
    save_play_data(sample_payload(minutes=60), "2026-09-20T10:00:00+00:00", db_file)
    save_play_data(sample_payload(minutes=0), "2026-09-20T11:00:00+00:00", db_file)
    with connect(db_file) as connection:
        rows = connection.execute("SELECT played_minutes FROM daily_play").fetchall()
    assert [row[0] for row in rows] == [0]


@pytest.mark.parametrize("minutes", [-1, None, "45", True, float("nan"), float("inf")])
def test_invalid_minutes_do_not_overwrite_valid_snapshot(tmp_path, minutes):
    db_file = tmp_path / "invalid.db"
    save_play_data(sample_payload(minutes=60), "2026-09-20T10:00:00+00:00", db_file)
    save_play_data(sample_payload(minutes=minutes), "2026-09-20T11:00:00+00:00", db_file)
    with connect(db_file) as connection:
        assert connection.execute("SELECT played_minutes FROM daily_play").fetchone()[0] == 60
