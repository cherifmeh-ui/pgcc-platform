"""PostgreSQL tests for document owner and department-level ACL."""
from __future__ import annotations

import os
from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints.documents import list_documents, preview_document
from app.models.document import Document
from app.models.user import User

DATABASE_URL = os.getenv("PGCC_INTEGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PGCC_INTEGRATION_DATABASE_URL not configured; requires migrated PostgreSQL",
)


@pytest.mark.asyncio
async def test_document_owner_and_department_scope_is_enforced_in_postgres():
    engine = create_async_engine(DATABASE_URL, pool_size=3, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    marker = uuid4().hex
    viewer = User(
        email=f"doc-acl-viewer-{marker}@example.invalid",
        full_name="Document ACL Viewer",
        role="viewer",
        password_hash="not-used",
        department="IT",
        is_active=True,
    )
    it_owner = User(
        email=f"doc-acl-it-{marker}@example.invalid",
        full_name="IT Document Owner",
        role="viewer",
        password_hash="not-used",
        department="IT",
        is_active=True,
    )
    finance_owner = User(
        email=f"doc-acl-finance-{marker}@example.invalid",
        full_name="Finance Document Owner",
        role="viewer",
        password_hash="not-used",
        department="Finance",
        is_active=True,
    )
    documents = []
    try:
        async with sessions() as setup:
            setup.add_all([viewer, it_owner, finance_owner])
            await setup.flush()
            documents = [
                Document(
                    title=f"IT procedure {marker}",
                    doc_type="PROCEDURE",
                    filename=f"doc-acl-{marker}-it.pdf",
                    content_text="IT procedure",
                    owner_id=it_owner.id,
                    department="IT",
                ),
                Document(
                    title=f"Finance procedure {marker}",
                    doc_type="PROCEDURE",
                    filename=f"doc-acl-{marker}-finance.pdf",
                    content_text="Finance procedure",
                    owner_id=finance_owner.id,
                    department="Finance",
                ),
                Document(
                    title=f"Viewer own contract {marker}",
                    doc_type="CONTRAT",
                    filename=f"doc-acl-{marker}-own.pdf",
                    content_text="viewer own restricted content",
                    owner_id=viewer.id,
                    department="IT",
                ),
                Document(
                    title=f"Finance contract {marker}",
                    doc_type="CONTRAT",
                    filename=f"doc-acl-{marker}-other.pdf",
                    content_text="finance restricted content",
                    owner_id=finance_owner.id,
                    department="Finance",
                ),
            ]
            setup.add_all(documents)
            await setup.commit()
            for document in documents:
                await setup.refresh(document)

        viewer_context = MagicMock(
            id=viewer.id, role="viewer", department="IT"
        )
        async with sessions() as db:
            rows = await list_documents(db=db, current_user=viewer_context)
            filenames = {row["filename"] for row in rows}
            assert documents[0].filename in filenames
            assert documents[1].filename not in filenames
            assert documents[2].filename in filenames
            assert documents[3].filename not in filenames

            own_preview = await preview_document(
                str(documents[2].id), db=db, current_user=viewer_context
            )
            assert own_preview["preview"] == "viewer own restricted content"

            with pytest.raises(HTTPException) as department_denied:
                await preview_document(
                    str(documents[1].id), db=db, current_user=viewer_context
                )
            assert department_denied.value.status_code == 404

            with pytest.raises(HTTPException) as owner_denied:
                await preview_document(
                    str(documents[3].id), db=db, current_user=viewer_context
                )
            assert owner_denied.value.status_code == 404
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(
                delete(Document).where(Document.filename.like(f"doc-acl-{marker}-%"))
            )
            await cleanup.execute(
                delete(User).where(User.email.in_([
                    f"doc-acl-viewer-{marker}@example.invalid",
                    f"doc-acl-it-{marker}@example.invalid",
                    f"doc-acl-finance-{marker}@example.invalid",
                ]))
            )
            await cleanup.commit()
        await engine.dispose()
