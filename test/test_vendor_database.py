"""The panel database loader: tables the library does not read."""

import logging

from custom_components.qolsys_panel.vendor.qolsys_controller.database.db import UNUSED_TABLE_URIS, QolsysDB

DB_LOGGER = "custom_components.qolsys_panel.vendor.qolsys_controller.database.db"


def test_known_unused_tables_are_skipped_quietly(caplog):
    """The two tables the panel ships that nothing reads log at debug, never as errors."""
    db = QolsysDB()
    payload = [{"uri": uri, "resultSet": [{"x": 1}]} for uri in sorted(UNUSED_TABLE_URIS)]
    with caplog.at_level(logging.DEBUG, logger=DB_LOGGER):
        db.load_db(payload)

    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
    skipped = [r.getMessage() for r in caplog.records if "skipping unused table" in r.getMessage()]
    assert len(skipped) == 2
    assert "(1 rows)" in skipped[0]


def test_a_table_the_library_has_never_seen_warns_once(caplog):
    """Something new from the panel is worth one warning, not three errors and not silence."""
    db = QolsysDB()
    payload = [{"uri": "content://com.qolsys.qolsysprovider.BrandNewProvider/brand_new", "resultSet": []}]
    with caplog.at_level(logging.DEBUG, logger=DB_LOGGER):
        db.load_db(payload)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "brand_new" in warnings[0].getMessage()
    assert "UNUSED_TABLE_URIS" in warnings[0].getMessage()
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


def test_empty_database_is_still_an_error(caplog):
    db = QolsysDB()
    with caplog.at_level(logging.ERROR):
        db.load_db(None)
    assert any("No Data Provided" in r.getMessage() for r in caplog.records)
