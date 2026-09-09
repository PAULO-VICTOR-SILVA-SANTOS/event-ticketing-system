from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# A generous busy_timeout so concurrent SQLite connections wait for the
# BEGIN IMMEDIATE lock below instead of failing fast with "database is
# locked" -- with several requests queued on the same write lock, the
# sqlite3 module's 5s default can be too short.
_connect_args = {"timeout": 30} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args)

if engine.dialect.name == "sqlite":
    # SQLite has no row-level locking, so `SELECT ... FOR UPDATE` (used to
    # serialize capacity checks, see routes/participants.py) silently compiles
    # to a plain SELECT and locks nothing. pysqlite also defers its actual
    # `BEGIN` until the first write, so even a write transaction doesn't hold
    # the database lock while an earlier SELECT in the same transaction runs.
    # Forcing every transaction to open with `BEGIN IMMEDIATE` grabs SQLite's
    # single database-wide write lock up front, which gives the same
    # serialization guarantee locally (dev/tests) that FOR UPDATE gives on
    # Postgres in production. Production never runs on sqlite, so this is a
    # no-op there.
    @event.listens_for(engine, "connect")
    def _sqlite_defer_to_explicit_begin(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _sqlite_begin_immediate(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
