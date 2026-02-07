import importlib
import logging
from unittest.mock import Mock, patch

import pytest

from tests.test_tracker_db import sample_payload


@pytest.fixture
def collector():
    # Import-time logging must not open files in the user's project.
    with patch("logging.FileHandler", return_value=logging.NullHandler()):
        return importlib.import_module("get_switch_data")


@pytest.mark.parametrize("failure", [None, "database", "json", "shape"])
def test_collection_exit_reflects_persistence(collector, monkeypatch, tmp_path, failure):
    response = Mock(status_code=200)
    response.json.return_value = {} if failure == "shape" else sample_payload()
    if failure == "json":
        response.json.side_effect = ValueError("invalid JSON")
    session = collector.NintendoSession.__new__(collector.NintendoSession)
    session.session = Mock()
    session.session.get.return_value = response
    session.session_token = "test-session"
    session.access_token = {"token_type": "Bearer", "access_token": "test-access"}
    session.timeout = 1
    session.ua = "test"
    monkeypatch.setattr(collector, "DB_FILE", tmp_path / "collection.db")
    monkeypatch.setattr(collector, "NintendoSession", lambda: session)
    if failure == "database":
        monkeypatch.setattr(collector, "save_to_database", lambda data: False)
    assert collector.main([]) == (1 if failure else 0)


def test_scheduler_propagates_collection_failure(monkeypatch):
    with patch("logging.FileHandler", return_value=logging.NullHandler()):
        scheduler = importlib.import_module("daily_collect")
    monkeypatch.setattr(
        scheduler.subprocess, "run",
        lambda *args, **kwargs: Mock(returncode=1, stdout="save failed", stderr=""),
    )
    assert scheduler.main() == 1
