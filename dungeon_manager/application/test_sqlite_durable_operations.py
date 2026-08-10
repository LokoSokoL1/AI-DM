import sqlite3

from dungeon_manager.adapters.sqlite_durable_operations import (
    SQLiteDurableOperationStore,
)

from .durable_operation_contracts import (
    DurableOperationLifecycle,
    DurableStoreDisposition,
)
from .test_durable_operation_contracts import identity, terminal_outcome


def test_sqlite_adapter_reserves_transitions_and_loads_exact_record_after_restart(
    tmp_path,
):
    path = tmp_path / "operations.sqlite"
    original = identity()
    store = SQLiteDurableOperationStore(path)

    reserved = store.reserve(original)
    started = store.mark_dispatch_started(original)
    terminal = store.record_terminal(original, terminal_outcome())
    restarted = SQLiteDurableOperationStore(path).lookup(original.key)

    assert reserved.disposition is DurableStoreDisposition.RESERVED
    assert reserved.record.lifecycle is DurableOperationLifecycle.RESERVED
    assert started.disposition is DurableStoreDisposition.SUCCESS
    assert started.record.lifecycle is DurableOperationLifecycle.DISPATCH_STARTED
    assert terminal.disposition is DurableStoreDisposition.SUCCESS
    assert terminal.record.lifecycle is DurableOperationLifecycle.TERMINAL
    assert restarted.disposition is DurableStoreDisposition.EXACT
    assert restarted.record == terminal.record


def test_sqlite_adapter_reports_incompatible_schema_without_replacing_it(tmp_path):
    path = tmp_path / "incompatible.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE unrelated(value TEXT)")
    connection.commit()
    connection.close()

    result = SQLiteDurableOperationStore(path).reserve(identity())

    assert result.disposition is DurableStoreDisposition.INCOMPATIBLE
    connection = sqlite3.connect(path)
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall() == [("unrelated",)]
    connection.close()


def test_sqlite_adapter_reports_malformed_record_without_disclosing_it(tmp_path):
    path = tmp_path / "malformed.sqlite"
    original = identity()
    store = SQLiteDurableOperationStore(path)
    store.reserve(original)
    connection = sqlite3.connect(path)
    connection.execute(
        "UPDATE operations SET integrity_digest = 'bad'"
    )
    connection.commit()
    connection.close()

    result = SQLiteDurableOperationStore(path).lookup(original.key)

    assert result.disposition is DurableStoreDisposition.MALFORMED
    assert result.record is None
