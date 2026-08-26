"""Async SQLite database layer for know-your-bible.

Provides the async engine, session factory, and ORM models used to
persist user settings and review results. SQLite runs in WAL mode with
foreign keys enforced.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import ForeignKey, String, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

## Default DB location: <repo>/data/app.db (independent of cwd)
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_DATABASE_URL = f"sqlite+aiosqlite:///{DATA_DIR / 'app.db'}"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _json_default(value):
    """JSON serializer fallback for non-native types (e.g. datetime)."""
    if isinstance(value, datetime):
        return value.isoformat()
    type_name = type(value).__name__
    raise TypeError(f"Object of type {type_name} is not JSON serializable")


def dumps_json(data) -> str:
    """Serialize a JSON-like structure to a string."""
    return json.dumps(data, default=_json_default)


def loads_json(raw: str | None):
    """Deserialize a JSON string, returning None for empty input."""
    return json.loads(raw) if raw else None


class UserSettings(Base):
    """Persisted per-user settings.

    Mirrors the shape of the ``settings`` dict cached in the TTLCache:
    selection criteria plus the serialized FSRS scheduler state.
    """

    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp: Mapped[str] = mapped_column(String, default="")
    translation: Mapped[str] = mapped_column(String, default="esv")
    selector: Mapped[str] = mapped_column(String, default="random")
    priority: Mapped[str] = mapped_column(String, default="weighted")
    testaments_json: Mapped[str] = mapped_column(String, default="[]")
    books_json: Mapped[str] = mapped_column(String, default="[]")
    chapters_json: Mapped[str] = mapped_column(String, default="{}")
    selected_verses: Mapped[str] = mapped_column(String, default="")
    verse_selection: Mapped[str] = mapped_column(String, default="")
    scheduler_dict_json: Mapped[str] = mapped_column(String, default="{}")

    review_results: Mapped[list["ReviewResult"]] = relationship(
        back_populates="settings", cascade="all, delete-orphan"
    )

    def to_settings_dict(self) -> dict:
        """Return the dict matching the cached ``settings`` entry."""
        return {
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "testaments": loads_json(self.testaments_json) or [],
            "books": loads_json(self.books_json) or [],
            "chapters": loads_json(self.chapters_json) or {},
            "selected_verses": self.selected_verses,
            "verse_selection": self.verse_selection,
            "translation": self.translation,
            "selector": self.selector,
            "priority": self.priority,
            "scheduler_dict": loads_json(self.scheduler_dict_json) or {},
        }

    @classmethod
    def from_settings_dict(cls, settings: dict) -> "UserSettings":
        """Build a row from the ``settings`` dict stored in cache."""
        return cls(
            user_id=settings["user_id"],
            timestamp=settings.get("timestamp", ""),
            translation=settings.get("translation", "esv"),
            selector=settings.get("selector", "random"),
            priority=settings.get("priority", "weighted"),
            testaments_json=dumps_json(settings.get("testaments", [])),
            books_json=dumps_json(settings.get("books", [])),
            chapters_json=dumps_json(settings.get("chapters", {})),
            selected_verses=settings.get("selected_verses", ""),
            verse_selection=settings.get("verse_selection", ""),
            scheduler_dict_json=dumps_json(settings.get("scheduler_dict", {})),
        )


class ReviewResult(Base):
    """A single graded review submission.

    Mirrors the ``result`` dict built in the ``submit`` handler.
    """

    __tablename__ = "review_results"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("user_settings.user_id", ondelete="CASCADE"),
        index=True,
    )
    timestamp: Mapped[str] = mapped_column(String)
    reference: Mapped[str] = mapped_column(String)
    submitted: Mapped[str] = mapped_column(String)
    stars: Mapped[int] = mapped_column(default=0)
    score: Mapped[int] = mapped_column(default=0)
    distance: Mapped[int] = mapped_column(default=0)
    timer: Mapped[float] = mapped_column(default=0.0)
    rating: Mapped[int] = mapped_column(default=0)
    card_dict_json: Mapped[str] = mapped_column(String, default="{}")
    due_str: Mapped[str] = mapped_column(String, default="")
    interval_secs: Mapped[float] = mapped_column(default=0.0)

    settings: Mapped["UserSettings"] = relationship(
        back_populates="review_results"
    )

    def to_result_dict(self) -> dict:
        """Return the dict matching the in-memory ``result`` entry."""
        return {
            "user_id": self.user_id,
            "id": self.id,
            "timestamp": self.timestamp,
            "reference": self.reference,
            "submitted": self.submitted,
            "stars": self.stars,
            "score": self.score,
            "distance": self.distance,
            "timer": self.timer,
            "rating": self.rating,
            "card_dict": loads_json(self.card_dict_json) or {},
            "due_str": self.due_str,
            "interval_secs": self.interval_secs,
        }


engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=False)


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    """Enable WAL mode and foreign keys on every new SQLite connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def install_sqlite_pragmas(sync_engine) -> None:
    """Attach the SQLite pragma listener to a sync engine."""
    event.listen(sync_engine, "connect", _set_sqlite_pragma)


if DATABASE_URL.startswith("sqlite"):
    install_sqlite_pragmas(engine.sync_engine)


async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


async def init_db() -> None:
    """Create all tables if they do not exist (idempotent)."""
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.split("///", 1)[-1]
        parent = Path(db_path).parent
        parent.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncSession:
    """Provide a session from the factory (context-managed by caller)."""
    return async_session_factory()
