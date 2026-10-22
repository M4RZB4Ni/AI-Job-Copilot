import psycopg

from app.config import DATABASE_URL
from app.core.exceptions import ConfigurationError
from app.models.chunk import DocumentChunk, SearchResult
from app.services.embeddings import EMBEDDING_DIM
from psycopg import sql


def _connect() -> psycopg.Connection:
    if not DATABASE_URL:
        raise ConfigurationError("DATABASE_URL must be configured.")
    return psycopg.connect(DATABASE_URL)


def _to_vector_text(vector: list[float]) -> str:
    return str(vector)


def init_schema() -> None:
    with _connect() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    source TEXT NOT NULL,
                    section TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    embedding vector({dim}) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            ).format(
                dim=sql.Literal(EMBEDDING_DIM)
            )
        )


def replace_all_chunks(chunks: list[DocumentChunk], vectors: list[list[float]]) -> None:
    # zip(chunks, vectors) pairs chunk 1 with vector 1, chunk 2 with vector 2, ...
    # The list comprehension builds one tuple per row, in the column order of the INSERT.
    rows = [
        (chunk.source, chunk.section, chunk.chunk_index, chunk.text, _to_vector_text(vector))
        for chunk, vector in zip(chunks, vectors)
    ]
    with _connect() as conn:
        # Both statements run in ONE transaction: either the old rows are replaced
        # by the new ones, or nothing changes at all.
        conn.execute("DELETE FROM document_chunks")
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO document_chunks (source, section, chunk_index, text, embedding)
                VALUES (%s, %s, %s, %s, %s::vector)
                """,
                rows,
            )


def search(query_vector: list[float], limit: int = 3) -> list[SearchResult]:
    vector_text = _to_vector_text(query_vector)
    with _connect() as conn:
        # <=> is pgvector's COSINE DISTANCE operator (0 = identical, bigger = further).
        # Similarity = 1 - distance, which equals the score our Python demo printed.
        # ORDER BY distance ASC puts the closest chunks first, LIMIT keeps the top few.
        rows = conn.execute(
            """
            SELECT source, section, text, 1 - (embedding <=> %s::vector) AS score
            FROM document_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vector_text, vector_text, limit),
        ).fetchall()
    return [
        SearchResult(source=row[0], section=row[1], text=row[2], score=row[3])
        for row in rows
    ]