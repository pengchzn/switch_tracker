"""SQLite schema and persistence helpers for Switch Tracker."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_FILE = PROJECT_ROOT / "switch_tracker.db"


def database_path() -> Path:
    """Return the configured database path."""
    configured = os.environ.get("SWITCH_TRACKER_DB")
    return Path(configured).expanduser().resolve() if configured else DEFAULT_DB_FILE


def connect(db_file: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    path = Path(db_file) if db_file is not None else database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def init_database(db_file: Optional[Union[str, Path]] = None) -> None:
    """Create the schema and safely migrate databases from older releases."""
    with connect(db_file) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS games (
                title_id TEXT PRIMARY KEY,
                title_name TEXT NOT NULL,
                image_url TEXT,
                device_type TEXT,
                chinese_name TEXT
            );
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title_id TEXT NOT NULL,
                first_played_at TEXT,
                last_played_at TEXT,
                total_played_days INTEGER,
                total_played_minutes INTEGER,
                collected_at TEXT NOT NULL,
                FOREIGN KEY (title_id) REFERENCES games (title_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS daily_play (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title_id TEXT NOT NULL,
                played_date TEXT NOT NULL,
                played_minutes INTEGER NOT NULL CHECK (played_minutes >= 0),
                collected_at TEXT NOT NULL,
                FOREIGN KEY (title_id) REFERENCES games (title_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS game_translations (
                title_id TEXT PRIMARY KEY,
                japanese_name TEXT,
                chinese_name TEXT,
                updated_at TEXT,
                FOREIGN KEY (title_id) REFERENCES games (title_id) ON DELETE CASCADE
            );
            """
        )
        translation_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(game_translations)")
        }
        if "updated_at" not in translation_columns:
            connection.execute("ALTER TABLE game_translations ADD COLUMN updated_at TEXT")

        # Old releases appended duplicate daily snapshots. Keep the latest
        # value before enforcing the natural key so collection is idempotent.
        connection.execute(
            """
            DELETE FROM daily_play
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY title_id, played_date
                               ORDER BY collected_at DESC, id DESC
                           ) AS row_number
                    FROM daily_play
                )
                WHERE row_number = 1
            )
            """
        )
        connection.executescript(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_daily_play_title_date
                ON daily_play (title_id, played_date);
            CREATE INDEX IF NOT EXISTS ix_daily_play_date
                ON daily_play (played_date DESC);
            CREATE INDEX IF NOT EXISTS ix_game_history_title_collected
                ON game_history (title_id, collected_at DESC);
            """
        )


def save_play_data(
    data: Mapping[str, Any],
    collected_at: str,
    db_file: Optional[Union[str, Path]] = None,
) -> int:
    """Persist one API snapshot and return the number of daily rows upserted."""
    init_database(db_file)
    daily_rows = 0
    with connect(db_file) as connection:
        for game in data.get("playHistories", []):
            title_id = game.get("titleId")
            title_name = game.get("titleName")
            if not title_id or not title_name:
                continue
            connection.execute(
                """
                INSERT INTO games (title_id, title_name, image_url, device_type)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(title_id) DO UPDATE SET
                    title_name = excluded.title_name,
                    image_url = excluded.image_url,
                    device_type = excluded.device_type
                """,
                (title_id, title_name, game.get("imageUrl"), game.get("deviceType")),
            )
            connection.execute(
                """
                INSERT INTO game_history (
                    title_id, first_played_at, last_played_at,
                    total_played_days, total_played_minutes, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    title_id,
                    game.get("firstPlayedAt"),
                    game.get("lastPlayedAt"),
                    game.get("totalPlayedDays"),
                    game.get("totalPlayedMinutes"),
                    collected_at,
                ),
            )

        for day_record in data.get("recentPlayHistories", []):
            played_date = day_record.get("playedDate")
            if not played_date:
                continue
            for game in day_record.get("dailyPlayHistories", []):
                title_id = game.get("titleId")
                minutes = game.get("totalPlayedMinutes")
                if not title_id or not isinstance(minutes, (int, float)) or minutes <= 0:
                    continue
                connection.execute(
                    """
                    INSERT INTO games (title_id, title_name, image_url, device_type)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(title_id) DO NOTHING
                    """,
                    (
                        title_id,
                        game.get("titleName") or title_id,
                        game.get("imageUrl"),
                        game.get("deviceType"),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO daily_play (
                        title_id, played_date, played_minutes, collected_at
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(title_id, played_date) DO UPDATE SET
                        played_minutes = excluded.played_minutes,
                        collected_at = excluded.collected_at
                    """,
                    (title_id, played_date, int(minutes), collected_at),
                )
                daily_rows += 1

        connection.execute(
            """
            UPDATE games
            SET chinese_name = (
                SELECT translations.chinese_name
                FROM game_translations AS translations
                WHERE translations.title_id = games.title_id
            )
            WHERE EXISTS (
                SELECT 1 FROM game_translations AS translations
                WHERE translations.title_id = games.title_id
                  AND translations.chinese_name != ''
            )
            """
        )
    return daily_rows
