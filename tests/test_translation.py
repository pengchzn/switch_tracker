import csv
import importlib
import logging
from unittest.mock import patch

import pytest

from tests.test_tracker_db import sample_payload
from tracker_db import connect, save_play_data


@pytest.fixture
def translation(monkeypatch, tmp_path):
    with patch("logging.FileHandler", return_value=logging.NullHandler()):
        module = importlib.import_module("game_translation")
    monkeypatch.setattr(module, "DB_FILE", tmp_path / "translation.db")
    monkeypatch.setattr(module, "TRANSLATION_CSV", tmp_path / "translations.csv")
    save_play_data(sample_payload(), "2026-09-20T10:00:00Z", module.DB_FILE)
    return module


def write_csv(module, rows):
    with module.TRANSLATION_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["title_id", "japanese_name", "chinese_name"])
        writer.writerows(rows)


@pytest.mark.parametrize("empty_name", ["", "   "])
def test_clear_translation_survives_apply_collection_and_export(translation, empty_name):
    write_csv(translation, [["0100TEST", "Test Game", "测试游戏"]])
    assert translation.import_translations_from_csv()
    write_csv(translation, [["0100TEST", "Test Game", empty_name]])
    assert translation.import_translations_from_csv()
    assert translation.apply_translations()
    save_play_data(sample_payload(), "2026-09-20T11:00:00Z", translation.DB_FILE)
    with connect(translation.DB_FILE) as connection:
        assert connection.execute("SELECT chinese_name FROM games").fetchone()[0] == ""
        assert connection.execute("SELECT chinese_name FROM game_translations").fetchone()[0] == ""
    assert translation.export_untranslated_games()
    with translation.TRANSLATION_CSV.open(encoding="utf-8") as handle:
        assert list(csv.DictReader(handle)) == [
            {"title_id": "0100TEST", "japanese_name": "Test Game", "chinese_name": ""}
        ]


def test_incomplete_row_does_not_clear_translation(translation):
    write_csv(translation, [["0100TEST", "Test Game", "测试游戏"]])
    assert translation.import_translations_from_csv()
    write_csv(translation, [["0100TEST", "Test Game"]])
    assert not translation.import_translations_from_csv()
    with connect(translation.DB_FILE) as connection:
        assert connection.execute("SELECT chinese_name FROM games").fetchone()[0] == "测试游戏"
