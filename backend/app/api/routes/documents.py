"""Document endpoints — upload, list, fetch, delete, and semantic search.

Upload extracts text, chunks it, embeds each chunk, and stores it in pgvector.
Search embeds the query and returns the nearest chunks (the retrieval primitive
that Step 14 wires into workflow grounding).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.config import Settings
from app.dependencies import get_document_repo, get_embedder_dep, get_settings_dep
from app.rag.embeddings import Embedder
from app.rag.extract import UnsupportedDocumentError
from app.rag.service import ChunkingConfig, ingest_document, search_documents
from app.repositories.documents import DocumentRepository
from app.schemas.document import (
    ChunkHitOut,
    DocumentList,
    DocumentOut,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _to_out(document) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        chunk_count=len(document.chunks),
        created_at=document.created_at,
    )


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    repo: DocumentRepository = Depends(get_document_repo),
    embedder: Embedder = Depends(get_embedder_dep),
    settings: Settings = Depends(get_settings_dep),
) -> DocumentOut:
    data = await file.read()
    try:
        document = ingest_document(
            filename=file.filename or "upload",
            content_type=file.content_type,
            data=data,
            embedder=embedder,
            chunking=ChunkingConfig(settings.chunk_size, settings.chunk_overlap),
        )
    except UnsupportedDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    saved = await repo.create(document)
    return _to_out(saved)


@router.get("", response_model=DocumentList)
async def list_documents(
    repo: DocumentRepository = Depends(get_document_repo),
    settings: Settings = Depends(get_settings_dep),
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
) -> DocumentList:
    effective_limit = min(limit or settings.api_default_page_size, settings.api_max_page_size)
    items, total = await repo.list(limit=effective_limit, offset=offset)
    return DocumentList(
        items=[_to_out(d) for d in items],
        total=total,
        limit=effective_limit,
        offset=offset,
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID,
    repo: DocumentRepository = Depends(get_document_repo),
) -> DocumentOut:
    document = await repo.get(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return _to_out(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    repo: DocumentRepository = Depends(get_document_repo),
) -> None:
    if not await repo.delete(document_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    repo: DocumentRepository = Depends(get_document_repo),
    embedder: Embedder = Depends(get_embedder_dep),
    settings: Settings = Depends(get_settings_dep),
) -> SearchResponse:
    hits = await search_documents(
        repo=repo,
        embedder=embedder,
        query=body.query,
        top_k=body.top_k or settings.rag_top_k,
    )
    return SearchResponse(
        query=body.query,
        results=[
            ChunkHitOut(
                chunk_id=h.chunk.id,
                document_id=h.chunk.document_id,
                chunk_index=h.chunk.chunk_index,
                content=h.chunk.content,
                score=h.score,
            )
            for h in hits
        ],
    )
