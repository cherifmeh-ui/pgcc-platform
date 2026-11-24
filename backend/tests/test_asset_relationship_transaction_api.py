from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.v1.endpoints.assets import (
    RelationshipCreate,
    create_asset_relationship,
    delete_asset_relationship,
)


ASSET_A = UUID("00000000-0000-0000-0000-000000000001")
ASSET_B = UUID("00000000-0000-0000-0000-000000000002")
RELATION_ID = UUID("00000000-0000-0000-0000-000000000003")


def _active_asset_rows():
    return [(ASSET_A, None, "Actif"), (ASSET_B, None, "Actif")]


def _db_for_relationship_create(*, graph_edges=None, commit_error=None):
    db = AsyncMock()
    advisory_lock_result = MagicMock()
    endpoint_result = MagicMock()
    endpoint_result.all.return_value = _active_asset_rows()
    graph_result = MagicMock()
    graph_result.all.return_value = graph_edges or []
    db.execute.side_effect = [advisory_lock_result, endpoint_result, graph_result]
    if commit_error is not None:
        db.commit.side_effect = commit_error
    return db


@pytest.mark.asyncio
async def test_create_relationship_rolls_back_and_propagates_unexpected_commit_error():
    db = _db_for_relationship_create(commit_error=RuntimeError("database connection lost"))

    with pytest.raises(RuntimeError, match="database connection lost"):
        await create_asset_relationship(
            asset_id=ASSET_A,
            data=RelationshipCreate(target_asset_id=ASSET_B, relationship_type="depends_on"),
            request=MagicMock(),
            db=db,
            current_user=MagicMock(email="admin@example.test"),
        )

    assert db.execute.await_count == 3
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_relationship_maps_integrity_error_to_conflict_and_rolls_back():
    db = _db_for_relationship_create(
        commit_error=IntegrityError("insert", {}, Exception("duplicate"))
    )

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await create_asset_relationship(
            asset_id=ASSET_A,
            data=RelationshipCreate(target_asset_id=ASSET_B, relationship_type="depends_on"),
            request=MagicMock(),
            db=db,
            current_user=MagicMock(email="admin@example.test"),
        )

    assert exc.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_relationship_rejects_cycle_before_insert():
    db = _db_for_relationship_create(graph_edges=[(ASSET_B, ASSET_A)])

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await create_asset_relationship(
            asset_id=ASSET_A,
            data=RelationshipCreate(target_asset_id=ASSET_B, relationship_type="depends_on"),
            request=MagicMock(),
            db=db,
            current_user=MagicMock(email="admin@example.test"),
        )

    assert exc.value.status_code == 422
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_relationship_rolls_back_and_propagates_commit_error():
    db = AsyncMock()
    relationship = MagicMock(
        id=RELATION_ID,
        source_asset_id=ASSET_A,
        target_asset_id=ASSET_B,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = relationship
    db.execute.return_value = result
    db.commit.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        await delete_asset_relationship(
            asset_id=ASSET_A,
            relationship_id=RELATION_ID,
            request=MagicMock(),
            db=db,
            current_user=MagicMock(email="admin@example.test"),
        )

    db.delete.assert_awaited_once_with(relationship)
    db.rollback.assert_awaited_once()



@pytest.mark.asyncio
async def test_create_relationship_flushes_asset_edge_before_audit_enqueue_and_commit(monkeypatch):
    db = _db_for_relationship_create()
    enqueue = AsyncMock()

    monkeypatch.setattr(
        "app.api.v1.endpoints.assets.enqueue_audit_event",
        enqueue,
    )

    order = []

    async def record_enqueue(*args, **kwargs):
        order.append("enqueue")

    db.flush.side_effect = lambda: order.append("flush")
    enqueue.side_effect = record_enqueue
    db.commit.side_effect = lambda: order.append("commit")

    await create_asset_relationship(
        asset_id=ASSET_A,
        data=RelationshipCreate(target_asset_id=ASSET_B, relationship_type="depends_on"),
        request=MagicMock(),
        db=db,
        current_user=MagicMock(email="admin@example.test"),
    )

    assert order == ["flush", "enqueue", "commit"]
    enqueue.assert_awaited_once()
    assert enqueue.await_args.args[0] is db
