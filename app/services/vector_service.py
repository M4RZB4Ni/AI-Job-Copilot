import psycopg

from app.config import DATABASE_URL
from app.core.exceptions import ConfigurationError
from app.models.chunk import DocumentChunk, SearchResult
from app.services.embeddings import EMBEDDING_DIM
from psycopg import sql
import logging 
from app.core.exceptions import ConfigurationError, VectorStoreError

logger = logging.getLogger(__name__)

def _connect() -> psycopg.Connection:
    if not DATABASE_URL:
        raise ConfigurationError("DATABASE_URL must be configured.")
    return psycopg.connect(DATABASE_URL)


def _to_vector_text(vector: list[float]) -> str:
    return str(vector)


def init_schema() -> None:
    with _connect() as conn:
        conn.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS source_hash TEXT")
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
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT source, section, text, 1 - (embedding <=> %s::vector) AS score
                FROM document_chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vector_text, vector_text, limit),
            ).fetchall()
    except psycopg.Error as error:
        # The real error (with SQL details) goes to OUR log only. The client gets a
        # short safe message, the same idea as the usage-logging error handler.
        # "from error" keeps the original error attached for debugging.
        logger.exception("Vector search failed")
        raise VectorStoreError(
            "Search is unavailable: check that the database is running and documents were ingested."
        ) from error
    return [
        SearchResult(source=row[0], section=row[1], text=row[2], score=row[3])
        for row in rows
    ]
    
    
def get_source_hashes() -> dict[str, str | None]:
    with _connect() as conn:
        # DISTINCT returns each (source, hash) pair once, because every chunk of a
        # file repeats the same values.
        rows = conn.execute("SELECT DISTINCT source, source_hash FROM document_chunks").fetchall()
    # Dict comprehension, like the one in chunking: {"cv.md": "ab12...", ...}
    return {row[0]: row[1] for row in rows}     


def replace_source(source: str, source_hash: str, chunks: list[DocumentChunk], vectors: list[list[float]]) -> None:
    rows = [
        (chunk.source, chunk.section, chunk.chunk_index, chunk.text, _to_vector_text(vector), source_hash)
        for chunk, vector in zip(chunks, vectors)
    ]
    with _connect() as conn:
        # Same transaction as before: the old rows of THIS file are swapped for the
        # new ones, and the other files are not touched.
        conn.execute("DELETE FROM document_chunks WHERE source = %s", (source,))
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO document_chunks (source, section, chunk_index, text, embedding, source_hash)
                VALUES (%s, %s, %s, %s, %s::vector, %s)
                """,
                rows,
            )
            
def delete_source(source: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM document_chunks WHERE source = %s", (source,))            