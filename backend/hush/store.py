"""Durable, encrypted persistence for the demo room state.

The demo keeps one mutable room in ``DemoService``. Without this module that
state lives only in process memory, so a restart during (say) the ~30-90s
on-chain confirmation window loses the receipt with no recovery path.

``StateStore`` snapshots the whole room state to a single row after every
mutation and restores it on startup:

- **Persistence** — SQLite file by default (zero infra), any SQLAlchemy URL via
  ``HUSH_DATABASE_URL``. Railway/Postgres: set that to the ``DATABASE_URL`` the
  platform injects (``postgres://`` / ``postgresql://`` schemes are rewritten to
  the psycopg driver automatically; ``pip install -e '.[postgres]'``).
- **At-rest encryption** — when ``HUSH_STATE_KEY`` (a Fernet key) is set, the
  entire JSON blob is Fernet-encrypted before it touches the database. Almost
  every field in the room state is private participant data (salts, raw
  constraint values, session tokens, source text), so the blob is sealed as a
  unit rather than field by field. Without the key the blob is stored as
  plaintext JSON and a warning is logged once.

Generate a key:  ``python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"``
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import StaticPool

logger = logging.getLogger("hush.store")

SCHEMA_VERSION = 1
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SQLITE_PATH = _REPO_ROOT / "hush-demo.db"

_metadata = MetaData()
room_state = Table(
    "room_state",
    _metadata,
    Column("room_id", String(128), primary_key=True),
    Column("schema_version", Integer, nullable=False),
    Column("encrypted", Boolean, nullable=False),
    Column("blob", LargeBinary, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


class StateFormatError(RuntimeError):
    """A stored blob could not be decoded (wrong key, corruption, schema drift)."""


def _database_url() -> str:
    raw = os.getenv("HUSH_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not raw:
        return f"sqlite:///{_DEFAULT_SQLITE_PATH.as_posix()}"
    # Railway/Heroku hand out bare postgres URLs; point them at psycopg v3.
    if raw.startswith("postgres://"):
        raw = "postgresql+psycopg://" + raw[len("postgres://") :]
    elif raw.startswith("postgresql://"):
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


def _fernet():
    key = os.getenv("HUSH_STATE_KEY")
    if not key:
        return None
    from cryptography.fernet import Fernet

    return Fernet(key.encode() if isinstance(key, str) else key)


class StateStore:
    """One row per decision room; the row holds the full serialized state."""

    def __init__(self, url: str | None = None) -> None:
        self._url = url or _database_url()
        url_obj = make_url(self._url)
        engine_kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
        connect_args: dict[str, Any] = {}
        if url_obj.get_backend_name() == "sqlite":
            # The background on-chain anchor thread persists from a different
            # thread than the one that built the engine.
            connect_args["check_same_thread"] = False
            if url_obj.database in (None, "", ":memory:"):
                engine_kwargs["poolclass"] = StaticPool
        self.engine: Engine = create_engine(
            self._url, connect_args=connect_args, **engine_kwargs
        )
        _metadata.create_all(self.engine)
        self._fernet = _fernet()
        if self._fernet is None:
            logger.warning(
                "HUSH_STATE_KEY 미설정 — 방 상태가 평문으로 저장됩니다. "
                "at-rest 암호화를 켜려면 Fernet 키를 설정하세요."
            )

    # -- introspection (health endpoint) ------------------------------------
    @property
    def backend(self) -> str:
        return make_url(self._url).get_backend_name()

    @property
    def at_rest_encrypted(self) -> bool:
        return self._fernet is not None

    def describe(self) -> dict[str, Any]:
        return {
            "persistence": self.backend,
            "at_rest_encryption": "fernet" if self.at_rest_encrypted else "none",
        }

    # -- codec ------------------------------------------------------------------
    def _seal(self, state: dict[str, Any]) -> tuple[bytes, bool]:
        raw = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if self._fernet is not None:
            return self._fernet.encrypt(raw), True
        return raw, False

    def _open(self, blob: bytes, encrypted: bool) -> dict[str, Any]:
        try:
            if encrypted:
                if self._fernet is None:
                    raise StateFormatError(
                        "저장된 상태가 암호화돼 있는데 HUSH_STATE_KEY가 없습니다."
                    )
                raw = self._fernet.decrypt(blob)
            else:
                raw = blob
            return json.loads(raw)
        except StateFormatError:
            raise
        except Exception as exc:  # cryptography.InvalidToken, JSONDecodeError, ...
            raise StateFormatError(f"저장된 상태를 복호화/파싱하지 못했습니다: {exc}") from exc

    # -- persistence ----------------------------------------------------------
    def save(self, room_id: str, state: dict[str, Any]) -> None:
        blob, encrypted = self._seal(state)
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            exists = conn.execute(
                select(room_state.c.room_id).where(room_state.c.room_id == room_id)
            ).first()
            values = {
                "schema_version": SCHEMA_VERSION,
                "encrypted": encrypted,
                "blob": blob,
                "updated_at": now,
            }
            if exists:
                conn.execute(
                    room_state.update().where(room_state.c.room_id == room_id).values(**values)
                )
            else:
                conn.execute(room_state.insert().values(room_id=room_id, **values))

    def load(self, room_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(
                    room_state.c.blob,
                    room_state.c.encrypted,
                    room_state.c.schema_version,
                ).where(room_state.c.room_id == room_id)
            ).first()
        if row is None:
            return None
        if row.schema_version != SCHEMA_VERSION:
            logger.warning(
                "room_state schema_version %s != %s — 무시하고 새로 시작합니다.",
                row.schema_version,
                SCHEMA_VERSION,
            )
            return None
        return self._open(row.blob, row.encrypted)

    def list_room_ids(self) -> list[str]:
        """Return persisted room identifiers without opening private blobs."""
        with self.engine.begin() as conn:
            rows = conn.execute(select(room_state.c.room_id).order_by(room_state.c.room_id)).all()
        return [row.room_id for row in rows]

    def clear(self, room_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(room_state.delete().where(room_state.c.room_id == room_id))

    def dispose(self) -> None:
        self.engine.dispose()
