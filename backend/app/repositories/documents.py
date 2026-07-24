"""Document persistence + vector similarity search behind an interface.

The SQLAlchemy implementation uses pgvector's cosine distance operator; an
in-memory fake (in tests) mirrors it with pure-Python cosine so the routes are
testable offline.
"""

from __future__ import annotations

import abc
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentChunk


class DocumentRepository(abc.ABC):
    @abc.abstractmethod
    async def create(self, document: Document) -> Document: ...

    @abc.abstractmethod
    async def get(self, document_id: UUID) -> Document | None: ...

    @abc.abstractmethod
    async def list(self, *, limit: int, offset: int) -> tuple[list[Document], int]: ...

    @abc.abstractmethod
    async def delete(self, document_id: UUID) -> bool: ...

    @abc.abstractmethod
    async def search(self, embedding: list[float], top_k: int) -> list[tuple[DocumentChunk, float]]:
        """Return the ``top_k`` nearest chunks as (chunk, cosine_distance)."""


class SqlAlchemyDocumentRepository(DocumentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, document: Document) -> Document:
        self._session.add(document)
        await self._session.commit()
        return await self.get(document.id)  # type: ignore[return-value]

    async def get(self, document_id: UUID) -> Document | None:
        stmt = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.chunks))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list(self, *, limit: int, offset: int) -> tuple[list[Document], int]:
        total = (
            await self._session.execute(select(func.count()).select_from(Document))
        ).scalar_one()
        stmt = (
            select(Document)
            .options(selectinload(Document.chunks))
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list((await self._session.execute(stmt)).scalars().all())
        return items, total

    async def delete(self, document_id: UUID) -> bool:
        document = await self._session.get(Document, document_id)
        if document is None:
            return False
        await self._session.delete(document)
        await self._session.commit()
        return True

    async def search(self, embedding: list[float], top_k: int) -> list[tuple[DocumentChunk, float]]:
        distance = DocumentChunk.embedding.cosine_distance(embedding)
        stmt = select(DocumentChunk, distance.label("distance")).order_by(distance).limit(top_k)
        rows = (await self._session.execute(stmt)).all()
        return [(chunk, float(dist)) for chunk, dist in rows]
