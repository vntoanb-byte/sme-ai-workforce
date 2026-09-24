"""Kiểm thử Alembic: migration khớp model, nâng cấp DB cũ tạo bằng create_all."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db import init_db
from app.db.base import Base


def _url(tmp_path: Path, name: str) -> str:
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def test_upgrade_head_matches_models(tmp_path: Path) -> None:
    url = _url(tmp_path, "fresh.db")
    init_db.upgrade_db(url)
    engine = create_engine(url)
    try:
        assert init_db.current_revision(engine) == init_db.head_revision()
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diff == []  # lược đồ sau migration == lược đồ model, không lệch
    finally:
        engine.dispose()


def test_legacy_create_all_db_is_stamped_then_upgraded(tmp_path: Path) -> None:
    url = _url(tmp_path, "legacy.db")
    engine = create_engine(url)
    # DB tạo bằng create_all TRƯỚC khi có bảng refresh_tokens (đúng tình trạng
    # data/app.db của Owner ở TASK-007).
    legacy_tables = [t for name, t in Base.metadata.tables.items() if name != "refresh_tokens"]
    Base.metadata.create_all(engine, tables=legacy_tables)
    assert "refresh_tokens" not in inspect(engine).get_table_names()
    engine.dispose()

    init_db.upgrade_db(url)
    engine = create_engine(url)
    try:
        assert "refresh_tokens" in inspect(engine).get_table_names()
        assert init_db.current_revision(engine) == init_db.head_revision()
    finally:
        engine.dispose()

    init_db.upgrade_db(url)  # chạy lại lần 2 không lỗi (idempotent)


def test_wait_for_schema_times_out_on_empty_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.db import session

    engine = create_engine(_url(tmp_path, "empty.db"))
    monkeypatch.setattr(session, "engine", engine)
    with pytest.raises(RuntimeError):
        init_db.wait_for_schema(timeout=0.2, interval=0.05)
    engine.dispose()
