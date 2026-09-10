"""Durable + encrypted room-state persistence (store.py, service wiring)."""

from __future__ import annotations

import json

import pytest
from cryptography.fernet import Fernet

from hush.service import DemoService
from hush.store import StateFormatError, StateStore, room_state
from sqlalchemy import select


def _file_store(tmp_path, monkeypatch, key: str | None = None):
    monkeypatch.delenv("HUSH_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    if key is None:
        monkeypatch.delenv("HUSH_STATE_KEY", raising=False)
    else:
        monkeypatch.setenv("HUSH_STATE_KEY", key)
    return StateStore(f"sqlite:///{(tmp_path / 'state.db').as_posix()}")


def test_save_load_roundtrip(tmp_path, monkeypatch):
    store = _file_store(tmp_path, monkeypatch)
    store.save("room-1", {"a": 1, "nested": {"b": [1, 2, 3]}})
    assert store.load("room-1") == {"a": 1, "nested": {"b": [1, 2, 3]}}
    assert store.load("missing") is None


def test_plaintext_when_no_key(tmp_path, monkeypatch):
    store = _file_store(tmp_path, monkeypatch)
    assert store.at_rest_encrypted is False
    store.save("room-1", {"secret": "15000"})
    with store.engine.begin() as conn:
        row = conn.execute(select(room_state.c.blob, room_state.c.encrypted)).first()
    assert row.encrypted is False
    assert json.loads(row.blob) == {"secret": "15000"}


def test_encrypted_at_rest_with_key(tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    store = _file_store(tmp_path, monkeypatch, key=key)
    assert store.at_rest_encrypted is True
    store.save("room-1", {"secret": "15000", "salt": "0xabc"})
    with store.engine.begin() as conn:
        row = conn.execute(select(room_state.c.blob, room_state.c.encrypted)).first()
    assert row.encrypted is True
    assert b"15000" not in row.blob and b"salt" not in row.blob
    with pytest.raises(Exception):
        json.loads(row.blob)
    assert store.load("room-1") == {"secret": "15000", "salt": "0xabc"}


def test_wrong_key_raises_state_format_error(tmp_path, monkeypatch):
    store = _file_store(tmp_path, monkeypatch, key=Fernet.generate_key().decode())
    store.save("room-1", {"x": 1})
    other = _file_store(tmp_path, monkeypatch, key=Fernet.generate_key().decode())
    with pytest.raises(StateFormatError):
        other.load("room-1")


def test_describe_reports_backend_and_encryption(tmp_path, monkeypatch):
    store = _file_store(tmp_path, monkeypatch)
    d = store.describe()
    assert d == {"persistence": "sqlite", "at_rest_encryption": "none"}


def test_postgres_url_scheme_is_rewritten(monkeypatch):
    monkeypatch.setenv("HUSH_DATABASE_URL", "postgres://u:p@localhost:5432/db")
    from hush import store as store_mod

    assert store_mod._database_url() == "postgresql+psycopg://u:p@localhost:5432/db"


# -- service restart semantics ------------------------------------------------


def _shared_store():
    return StateStore("sqlite://")  # in-memory, StaticPool keeps it alive


def test_service_restores_state_from_store(monkeypatch):
    monkeypatch.setenv("HUSH_DEMO_ADMIN_KEY", "k")
    store = _shared_store()

    first = DemoService(store=store)
    first.seed_confirmed_inputs()
    assert first.run_decision()["status"] == "INFEASIBLE"

    # "restart": brand-new service, same store
    second = DemoService(store=store)
    assert second.room_status == "NEGOTIATING"
    assert len(second._active_constraints()) == 4

    second.accept_proposal("A")
    assert second.run_decision()["status"] == "FEASIBLE"
    assert second.verify("A")["status"] == "VERIFIED"


def test_reset_is_persisted(monkeypatch):
    store = _shared_store()
    svc = DemoService(store=store)
    svc.seed_confirmed_inputs()
    svc.reset()
    assert DemoService(store=store).room_status == "COLLECTING"
