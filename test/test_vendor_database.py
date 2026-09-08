"""The panel database loader: tables the library does not know are not errors."""

import logging

from custom_components.qolsys_panel.vendor.qolsys_controller.database.db import QolsysDB


def test_unknown_table_is_skipped_quietly(caplog):
    """A table the library never reads (the panel ships several) logs at debug, not error."""
    db = QolsysDB()
    payload = [
        {"uri": "content://com.qolsys.qolsysprovider.YaleAuthIdsProvider/yale_auth_ids", "resultSet": []},
        {"uri": "content://com.qolsys.qolsysprovider.ImeDataContentProvider/ime_data", "resultSet": [{"x": 1}]},
    ]
    with caplog.at_level(logging.DEBUG, logger="custom_components.qolsys_panel.vendor.qolsys_controller.database.db"):
        db.load_db(payload)

    errors = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert errors == []
    skipped = [r.getMessage() for r in caplog.records if "skipping table" in r.getMessage()]
    assert len(skipped) == 2
    assert "ime_data" in skipped[1] and "(1 rows)" in skipped[1]


def test_empty_database_is_still_an_error(caplog):
    db = QolsysDB()
    with caplog.at_level(logging.ERROR):
        db.load_db(None)
    assert any("No Data Provided" in r.getMessage() for r in caplog.records)
