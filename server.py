"""Local Flask dashboard for Switch Tracker."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Union

from flask import Flask, current_app, jsonify, render_template, send_from_directory
from werkzeug.exceptions import HTTPException

from tracker_db import connect, database_path, init_database

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent


def create_app(db_file: Optional[Union[str, Path]] = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["DATABASE"] = str(db_file or database_path())
    app.config["JSON_AS_ASCII"] = False
    init_database(app.config["DATABASE"])

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self'"
        )
        return response

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/styles.css")
    def styles():
        return send_from_directory(PROJECT_ROOT, "styles.css")

    @app.get("/script.js")
    def script():
        return send_from_directory(PROJECT_ROOT, "script.js")

    @app.get("/static/<path:filename>")
    def static_asset(filename: str):
        return send_from_directory(PROJECT_ROOT / "static", filename)

    @app.get("/health")
    def health():
        with _connection() as connection:
            connection.execute("SELECT 1").fetchone()
        return jsonify({"status": "ok"})

    @app.get("/api/monthly_playtime")
    def monthly_playtime():
        with _connection() as connection:
            rows = connection.execute(
                """
                SELECT strftime('%Y-%m', played_date) AS month,
                       SUM(played_minutes) AS total_minutes
                FROM daily_play
                GROUP BY month
                ORDER BY month
                """
            ).fetchall()
        return jsonify({row["month"]: row["total_minutes"] for row in rows})

    @app.get("/api/games")
    def games():
        with _connection() as connection:
            rows = connection.execute(
                """
                SELECT g.title_id,
                       COALESCE(NULLIF(g.chinese_name, ''), g.title_name) AS display_name,
                       g.title_name AS original_name,
                       g.image_url,
                       g.device_type,
                       h.total_played_days,
                       h.total_played_minutes,
                       h.last_played_at,
                       h.first_played_at
                FROM games AS g
                JOIN game_history AS h ON h.id = (
                    SELECT latest.id
                    FROM game_history AS latest
                    WHERE latest.title_id = g.title_id
                    ORDER BY latest.collected_at DESC, latest.id DESC
                    LIMIT 1
                )
                ORDER BY h.total_played_minutes DESC, display_name COLLATE NOCASE
                """
            ).fetchall()
        return jsonify(
            [
                {
                    "title_id": row["title_id"],
                    "name": row["display_name"],
                    "original_name": row["original_name"],
                    "image_url": row["image_url"],
                    "device_type": row["device_type"],
                    "total_played_days": row["total_played_days"],
                    "total_played_minutes": row["total_played_minutes"],
                    "last_played_at": row["last_played_at"],
                    "first_played_at": row["first_played_at"],
                }
                for row in rows
            ]
        )

    @app.get("/api/game/<title_id>/daily")
    def game_daily(title_id: str):
        with _connection() as connection:
            game = connection.execute(
                """
                SELECT title_id,
                       COALESCE(NULLIF(chinese_name, ''), title_name) AS display_name,
                       image_url
                FROM games WHERE title_id = ?
                """,
                (title_id,),
            ).fetchone()
            if game is None:
                return jsonify({"error": "Game not found"}), 404
            rows = connection.execute(
                """
                SELECT played_date, played_minutes
                FROM daily_play
                WHERE title_id = ?
                ORDER BY played_date
                """,
                (title_id,),
            ).fetchall()
        return jsonify(
            {
                "title_id": game["title_id"],
                "name": game["display_name"],
                "image_url": game["image_url"],
                "daily_data": [
                    {"date": row["played_date"], "minutes": row["played_minutes"]}
                    for row in rows
                ],
            }
        )

    @app.get("/api/history")
    def history():
        with _connection() as connection:
            rows = connection.execute(
                """
                SELECT d.played_date,
                       d.title_id,
                       COALESCE(NULLIF(g.chinese_name, ''), g.title_name) AS display_name,
                       g.image_url,
                       d.played_minutes
                FROM daily_play AS d
                JOIN games AS g ON g.title_id = d.title_id
                ORDER BY d.played_date DESC, d.played_minutes DESC
                """
            ).fetchall()
        return jsonify(_group_history(rows))

    @app.get("/api/recent_activities")
    def recent_activities():
        with _connection() as connection:
            rows = connection.execute(
                """
                SELECT d.played_date,
                       d.title_id,
                       COALESCE(NULLIF(g.chinese_name, ''), g.title_name) AS display_name,
                       g.image_url,
                       d.played_minutes
                FROM daily_play AS d
                JOIN games AS g ON g.title_id = d.title_id
                WHERE d.played_date IN (
                    SELECT played_date FROM daily_play
                    GROUP BY played_date
                    ORDER BY played_date DESC
                    LIMIT 7
                )
                ORDER BY d.played_date DESC, d.played_minutes DESC
                """
            ).fetchall()
        activities = []
        for day in _group_history(rows):
            activities.append(
                {
                    "playedDate": day["date"],
                    "dailyPlayHistories": [
                        {
                            "titleId": game["title_id"],
                            "titleName": game["name"],
                            "imageUrl": game["image_url"],
                            "totalPlayedMinutes": game["minutes"],
                        }
                        for game in day["games"]
                    ],
                }
            )
        return jsonify({"recentPlayHistories": activities})

    @app.errorhandler(Exception)
    def unhandled_error(error):
        if isinstance(error, HTTPException):
            return error
        LOGGER.exception("Unhandled request error", exc_info=error)
        return jsonify({"error": "Internal server error"}), 500

    return app


def _connection():
    return connect(current_app.config["DATABASE"])


def _group_history(rows):
    by_date: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_date.setdefault(row["played_date"], []).append(
            {
                "title_id": row["title_id"],
                "name": row["display_name"],
                "image_url": row["image_url"],
                "minutes": row["played_minutes"],
            }
        )
    return [{"date": date, "games": games} for date, games in by_date.items()]


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    host = os.environ.get("SWITCH_TRACKER_HOST", "127.0.0.1")
    port = int(os.environ.get("SWITCH_TRACKER_PORT", "8000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app = create_app()
    app.run(host=host, port=port, debug=debug)
