"""RAG unit tests: chunking, embeddings, extraction, and the document routes."""

import pytest
from app.rag.chunking import chunk_text
from app.rag.embeddings import EMBEDDING_DIM, HashingEmbedder
from app.rag.extract import UnsupportedDocumentError, extract_text

pytestmark = pytest.mark.unit


# --- chunking ---


def test_chunking_overlaps_and_covers_text():
    text = "abcdefghij" * 10  # 100 chars
    chunks = chunk_text(text, chunk_size=40, overlap=10)
    assert len(chunks) >= 3
    assert chunks[0] == text[:40]
    # consecutive chunks overlap by `overlap` chars (step = 30)
    assert chunks[1].startswith(text[30:40])


def test_chunking_empty_text():
    assert chunk_text("   ", chunk_size=100, overlap=10) == []


def test_chunking_rejects_bad_overlap():
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=10, overlap=10)


# --- embeddings ---


def test_embedding_dimension_and_determinism():
    emb = HashingEmbedder()
    v1 = emb.embed_one("invoice payment terms")
    v2 = emb.embed_one("invoice payment terms")
    assert len(v1) == EMBEDDING_DIM
    assert v1 == v2  # deterministic


def test_similar_text_scores_higher_than_unrelated():
    emb = HashingEmbedder()

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    query = emb.embed_one("invoice payment terms and due date")
    related = emb.embed_one("the invoice payment is due on these terms")
    unrelated = emb.embed_one("weather forecast for the mountains tomorrow")
    assert cos(query, related) > cos(query, unrelated)


# --- extraction ---


def test_extract_text_from_plaintext():
    assert extract_text("notes.txt", "text/plain", b"hello world") == "hello world"


def test_extract_rejects_unsupported_type():
    with pytest.raises(UnsupportedDocumentError):
        extract_text("image.png", "image/png", b"\x89PNG")


# --- routes (in-memory repo + fake embedder) ---


def _upload(client, name: str, text: str):
    return client.post(
        "/api/documents",
        files={"file": (name, text.encode(), "text/plain")},
    )


def test_upload_chunks_and_embeds(document_client):
    resp = _upload(document_client, "doc.txt", "some content " * 200)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["filename"] == "doc.txt"
    assert body["chunk_count"] >= 1
    assert body["size_bytes"] > 0


def test_upload_rejects_unsupported_type(document_client):
    resp = document_client.post(
        "/api/documents", files={"file": ("x.png", b"\x89PNG", "image/png")}
    )
    assert resp.status_code == 415


def test_search_returns_most_relevant_chunk(document_client):
    _upload(document_client, "invoices.txt", "Invoice payment terms are net 30 days.")
    _upload(document_client, "weather.txt", "The mountain weather forecast is sunny.")
    resp = document_client.post(
        "/api/documents/search", json={"query": "invoice payment terms", "top_k": 1}
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert "Invoice payment" in results[0]["content"]
    assert results[0]["score"] > 0


def test_list_and_delete_document(document_client):
    doc = _upload(document_client, "d.txt", "hello content here").json()
    assert document_client.get("/api/documents").json()["total"] == 1
    assert document_client.delete(f"/api/documents/{doc['id']}").status_code == 204
    assert document_client.get(f"/api/documents/{doc['id']}").status_code == 404
