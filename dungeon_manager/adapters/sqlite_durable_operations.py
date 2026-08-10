"""SQLite adapter for the Phase 2 M3 durable-operation port."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Optional

from dungeon_manager.application.durable_operation_contracts import (
    CampaignOperationKey,
    CanonicalOperationIdentity,
    DurableOperationLifecycle,
    DurableOperationRecord,
    DurableStoreDisposition,
    DurableStoreResult,
    DurableTerminalOutcome,
)


DURABLE_OPERATION_STORAGE_FORMAT = (
    "dungeon_manager.phase2_m3_operations.sqlite"
)
DURABLE_OPERATION_STORAGE_SCHEMA_VERSION = 1
DURABLE_OPERATION_STORE_ID = "controlled-fixture-durable-operations"
_METADATA = {
    "format": DURABLE_OPERATION_STORAGE_FORMAT,
    "schema_version": DURABLE_OPERATION_STORAGE_SCHEMA_VERSION,
    "store_id": DURABLE_OPERATION_STORE_ID,
}


class _StoreProblem(Exception):
    def __init__(self, disposition: DurableStoreDisposition) -> None:
        self.disposition = disposition


def _record_digest(
    campaign_id: str,
    operation_key: str,
    identity_json: str,
    fingerprint: str,
    kind: str,
    lifecycle: str,
    terminal_json: Optional[str],
) -> str:
    parts = (
        "phase2-m3-operation-record-v1",
        campaign_id,
        operation_key,
        identity_json,
        fingerprint,
        kind,
        lifecycle,
        "" if terminal_json is None else terminal_json,
    )
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


class SQLiteDurableOperationStore:
    """Path-bound transactional store for campaign-scoped operation keys."""

    def __init__(self, path: str | Path) -> None:
        if not isinstance(path, (str, Path)):
            raise ValueError("Durable-operation database path is invalid.")
        self.__path = Path(path)
        if not str(self.__path):
            raise ValueError("Durable-operation database path must not be empty.")

    @property
    def path(self) -> Path:
        return self.__path

    def lookup(self, key: CampaignOperationKey) -> DurableStoreResult:
        if not isinstance(key, CampaignOperationKey):
            raise ValueError("Operation lookup key must be typed.")
        connection = None
        try:
            connection = self._open(write=False)
            record = self._read_record(connection, key)
            connection.commit()
            if record is None:
                return DurableStoreResult(DurableStoreDisposition.NOT_FOUND)
            return DurableStoreResult(DurableStoreDisposition.EXACT, record)
        except _StoreProblem as problem:
            self._rollback(connection)
            return DurableStoreResult(problem.disposition)
        except (sqlite3.Error, OSError):
            self._rollback(connection)
            return DurableStoreResult(DurableStoreDisposition.UNAVAILABLE)
        finally:
            if connection is not None:
                connection.close()

    def reserve(
        self, identity: CanonicalOperationIdentity
    ) -> DurableStoreResult:
        if not isinstance(identity, CanonicalOperationIdentity):
            raise ValueError("Operation reservation identity must be typed.")
        connection = None
        try:
            connection = self._open(write=True)
            existing = self._read_record(connection, identity.key)
            if existing is not None:
                connection.commit()
                if existing.identity == identity:
                    return DurableStoreResult(
                        DurableStoreDisposition.EXACT, existing
                    )
                return DurableStoreResult(DurableStoreDisposition.COLLISION)
            record = DurableOperationRecord(
                identity, DurableOperationLifecycle.RESERVED
            )
            self._insert_record(connection, record)
            connection.commit()
            return DurableStoreResult(DurableStoreDisposition.RESERVED, record)
        except sqlite3.IntegrityError:
            self._rollback(connection)
            return DurableStoreResult(DurableStoreDisposition.CONFLICT)
        except _StoreProblem as problem:
            self._rollback(connection)
            return DurableStoreResult(problem.disposition)
        except (sqlite3.Error, OSError):
            self._rollback(connection)
            return DurableStoreResult(DurableStoreDisposition.UNAVAILABLE)
        finally:
            if connection is not None:
                connection.close()

    def mark_dispatch_started(
        self, identity: CanonicalOperationIdentity
    ) -> DurableStoreResult:
        return self._transition(
            identity,
            DurableOperationLifecycle.RESERVED,
            DurableOperationLifecycle.DISPATCH_STARTED,
            None,
        )

    def record_terminal(
        self,
        identity: CanonicalOperationIdentity,
        outcome: DurableTerminalOutcome,
    ) -> DurableStoreResult:
        if not isinstance(outcome, DurableTerminalOutcome):
            raise ValueError("Terminal operation outcome must be typed.")
        return self._transition(
            identity,
            DurableOperationLifecycle.DISPATCH_STARTED,
            DurableOperationLifecycle.TERMINAL,
            outcome,
        )

    def _transition(
        self,
        identity: CanonicalOperationIdentity,
        expected: DurableOperationLifecycle,
        lifecycle: DurableOperationLifecycle,
        outcome: Optional[DurableTerminalOutcome],
    ) -> DurableStoreResult:
        if not isinstance(identity, CanonicalOperationIdentity):
            raise ValueError("Operation transition identity must be typed.")
        connection = None
        try:
            connection = self._open(write=True)
            existing = self._read_record(connection, identity.key)
            if existing is None:
                connection.rollback()
                return DurableStoreResult(DurableStoreDisposition.NOT_FOUND)
            if existing.identity != identity:
                connection.rollback()
                return DurableStoreResult(DurableStoreDisposition.COLLISION)
            if existing.lifecycle is not expected:
                connection.rollback()
                return DurableStoreResult(DurableStoreDisposition.CONFLICT)
            terminal_json = None if outcome is None else outcome.canonical_json
            digest = _record_digest(
                identity.key.campaign_id,
                identity.key.operation_key,
                identity.canonical_json,
                identity.fingerprint,
                identity.kind.value,
                lifecycle.value,
                terminal_json,
            )
            cursor = connection.execute(
                "UPDATE operations SET lifecycle = ?, terminal_json = ?, "
                "integrity_digest = ? WHERE campaign_id = ? AND "
                "operation_key = ? AND fingerprint = ? AND lifecycle = ?",
                (
                    lifecycle.value,
                    terminal_json,
                    digest,
                    identity.key.campaign_id,
                    identity.key.operation_key,
                    identity.fingerprint,
                    expected.value,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return DurableStoreResult(DurableStoreDisposition.CONFLICT)
            record = self._read_record(connection, identity.key)
            if record is None or record.lifecycle is not lifecycle:
                raise _StoreProblem(DurableStoreDisposition.MALFORMED)
            connection.commit()
            return DurableStoreResult(DurableStoreDisposition.SUCCESS, record)
        except _StoreProblem as problem:
            self._rollback(connection)
            return DurableStoreResult(problem.disposition)
        except (sqlite3.Error, OSError):
            self._rollback(connection)
            return DurableStoreResult(DurableStoreDisposition.UNAVAILABLE)
        finally:
            if connection is not None:
                connection.close()

    def _open(self, *, write: bool) -> sqlite3.Connection:
        if self.__path.exists() and not self.__path.is_file():
            raise _StoreProblem(DurableStoreDisposition.UNAVAILABLE)
        new_store = not self.__path.exists()
        if new_store:
            try:
                self.__path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise _StoreProblem(DurableStoreDisposition.UNAVAILABLE) from error
        connection = sqlite3.connect(self.__path, timeout=0)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE" if write or new_store else "BEGIN")
            if new_store:
                self._create_schema(connection)
            self._validate_schema(connection)
            return connection
        except Exception:
            connection.close()
            raise

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            "CREATE TABLE metadata (key TEXT PRIMARY KEY, value NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE operations ("
            "campaign_id TEXT NOT NULL, "
            "operation_key TEXT NOT NULL, "
            "identity_json TEXT NOT NULL, "
            "fingerprint TEXT NOT NULL, "
            "kind TEXT NOT NULL, "
            "lifecycle TEXT NOT NULL, "
            "terminal_json TEXT, "
            "integrity_digest TEXT NOT NULL, "
            "PRIMARY KEY(campaign_id, operation_key))"
        )
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            tuple(_METADATA.items()),
        )

    @staticmethod
    def _validate_schema(connection: sqlite3.Connection) -> None:
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            if tables != {"metadata", "operations"}:
                raise _StoreProblem(DurableStoreDisposition.INCOMPATIBLE)
            rows = connection.execute(
                "SELECT key, value FROM metadata"
            ).fetchall()
        except sqlite3.Error as error:
            raise _StoreProblem(DurableStoreDisposition.MALFORMED) from error
        metadata = {}
        for key, value in rows:
            if not isinstance(key, str) or key in metadata:
                raise _StoreProblem(DurableStoreDisposition.MALFORMED)
            metadata[key] = value
        if set(metadata) != set(_METADATA):
            raise _StoreProblem(DurableStoreDisposition.MALFORMED)
        if metadata["format"] != DURABLE_OPERATION_STORAGE_FORMAT:
            raise _StoreProblem(DurableStoreDisposition.INCOMPATIBLE)
        if metadata["store_id"] != DURABLE_OPERATION_STORE_ID:
            raise _StoreProblem(DurableStoreDisposition.INCOMPATIBLE)
        version = metadata["schema_version"]
        if not isinstance(version, int) or isinstance(version, bool):
            raise _StoreProblem(DurableStoreDisposition.MALFORMED)
        if version != DURABLE_OPERATION_STORAGE_SCHEMA_VERSION:
            raise _StoreProblem(DurableStoreDisposition.INCOMPATIBLE)
        metadata_columns = connection.execute(
            "PRAGMA table_info(metadata)"
        ).fetchall()
        operation_columns = connection.execute(
            "PRAGMA table_info(operations)"
        ).fetchall()
        metadata_shape = tuple(
            (row[1], row[2], row[3], row[4], row[5])
            for row in metadata_columns
        )
        operation_shape = tuple(
            (row[1], row[2], row[3], row[4], row[5])
            for row in operation_columns
        )
        if metadata_shape != (
            ("key", "TEXT", 0, None, 1),
            ("value", "", 1, None, 0),
        ) or operation_shape != (
            ("campaign_id", "TEXT", 1, None, 1),
            ("operation_key", "TEXT", 1, None, 2),
            ("identity_json", "TEXT", 1, None, 0),
            ("fingerprint", "TEXT", 1, None, 0),
            ("kind", "TEXT", 1, None, 0),
            ("lifecycle", "TEXT", 1, None, 0),
            ("terminal_json", "TEXT", 0, None, 0),
            ("integrity_digest", "TEXT", 1, None, 0),
        ):
            raise _StoreProblem(DurableStoreDisposition.INCOMPATIBLE)

    @staticmethod
    def _read_record(
        connection: sqlite3.Connection,
        key: CampaignOperationKey,
    ) -> Optional[DurableOperationRecord]:
        try:
            rows = connection.execute(
                "SELECT campaign_id, operation_key, identity_json, fingerprint, "
                "kind, lifecycle, terminal_json, integrity_digest FROM operations "
                "WHERE campaign_id = ? AND operation_key = ?",
                (key.campaign_id, key.operation_key),
            ).fetchall()
        except sqlite3.Error as error:
            raise _StoreProblem(DurableStoreDisposition.MALFORMED) from error
        if not rows:
            return None
        if len(rows) != 1:
            raise _StoreProblem(DurableStoreDisposition.MALFORMED)
        (
            campaign_id,
            operation_key,
            identity_json,
            fingerprint,
            kind,
            lifecycle_value,
            terminal_json,
            digest,
        ) = rows[0]
        if not all(
            isinstance(value, str)
            for value in (
                campaign_id,
                operation_key,
                identity_json,
                fingerprint,
                kind,
                lifecycle_value,
                digest,
            )
        ) or (terminal_json is not None and not isinstance(terminal_json, str)):
            raise _StoreProblem(DurableStoreDisposition.MALFORMED)
        if digest != _record_digest(
            campaign_id,
            operation_key,
            identity_json,
            fingerprint,
            kind,
            lifecycle_value,
            terminal_json,
        ):
            raise _StoreProblem(DurableStoreDisposition.MALFORMED)
        try:
            identity = CanonicalOperationIdentity.from_canonical_json(identity_json)
            lifecycle = DurableOperationLifecycle(lifecycle_value)
            outcome = (
                None
                if terminal_json is None
                else DurableTerminalOutcome.from_json(terminal_json)
            )
            record = DurableOperationRecord(identity, lifecycle, outcome)
        except (KeyError, TypeError, ValueError):
            raise _StoreProblem(DurableStoreDisposition.MALFORMED) from None
        if (
            identity.key != key
            or campaign_id != key.campaign_id
            or operation_key != key.operation_key
            or fingerprint != identity.fingerprint
            or kind != identity.kind.value
        ):
            raise _StoreProblem(DurableStoreDisposition.MALFORMED)
        return record

    @staticmethod
    def _insert_record(
        connection: sqlite3.Connection,
        record: DurableOperationRecord,
    ) -> None:
        identity = record.identity
        terminal_json = (
            None
            if record.terminal_outcome is None
            else record.terminal_outcome.canonical_json
        )
        digest = _record_digest(
            identity.key.campaign_id,
            identity.key.operation_key,
            identity.canonical_json,
            identity.fingerprint,
            identity.kind.value,
            record.lifecycle.value,
            terminal_json,
        )
        connection.execute(
            "INSERT INTO operations(campaign_id, operation_key, identity_json, "
            "fingerprint, kind, lifecycle, terminal_json, integrity_digest) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                identity.key.campaign_id,
                identity.key.operation_key,
                identity.canonical_json,
                identity.fingerprint,
                identity.kind.value,
                record.lifecycle.value,
                terminal_json,
                digest,
            ),
        )

    @staticmethod
    def _rollback(connection: Optional[sqlite3.Connection]) -> None:
        if connection is not None:
            try:
                connection.rollback()
            except sqlite3.Error:
                pass
