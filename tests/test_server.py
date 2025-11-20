from server import create_app
from tests.test_tracker_db import sample_payload
from tracker_db import save_play_data


def build_client(tmp_path):
    db_file = tmp_path / "web.db"
    save_play_data(sample_payload(), "2025-01-02T10:00:00+00:00", db_file)
    app = create_app(db_file)
    app.config.update(TESTING=True)
    return app.test_client()


def test_dashboard_and_health(tmp_path):
    client = build_client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert "Switch Tracker" in response.get_data(as_text=True)
    assert response.headers["X-Frame-Options"] == "DENY"
    assert client.get("/health").get_json() == {"status": "ok"}


def test_api_returns_latest_game_and_daily_data(tmp_path):
    client = build_client(tmp_path)

    games = client.get("/api/games").get_json()
    assert games[0]["title_id"] == "0100TEST"
    assert games[0]["total_played_minutes"] == 120

    history = client.get("/api/history").get_json()
    assert history == [
        {
            "date": "2025-01-02",
            "games": [
                {
                    "image_url": "https://example.com/game.png",
                    "minutes": 45,
                    "name": "Test Game",
                    "title_id": "0100TEST",
                }
            ],
        }
    ]


def test_sensitive_repository_files_are_not_served(tmp_path):
    client = build_client(tmp_path)
    assert client.get("/config/tokens.json").status_code == 404
    assert client.get("/switch_tracker.db").status_code == 404
    assert client.get("/.git/config").status_code == 404
