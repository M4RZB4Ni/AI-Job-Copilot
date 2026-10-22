from app.config import DATA_DIR
from app.services.chunking import chunk_directory
from app.services.embeddings import embed_documents
from app.services.vector_store import init_schema, replace_all_chunks


def main() -> None:
    chunks = chunk_directory(DATA_DIR)
    if not chunks:
        print(f"No chunks found in {DATA_DIR}")
        return
    # Same two steps as the earlier demo: chunk the files, then embed every chunk.
    vectors = embed_documents([chunk.text for chunk in chunks])
    init_schema()
    replace_all_chunks(chunks, vectors)
    print(f"Ingested {len(chunks)} chunks from {DATA_DIR}")


if __name__ == "__main__":
    main()