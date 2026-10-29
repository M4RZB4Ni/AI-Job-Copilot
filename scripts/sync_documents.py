import hashlib

from app.config import DATA_DIR
from app.core.exceptions import ConfigurationError
from app.services.chunking import chunk_markdown
from app.services.embeddings import embed_documents
from app.services.vector_service import delete_source, get_source_hashes, init_schema, replace_source


def file_hash(text: str) -> str:
    # A hash is a fingerprint: the same text always gives the same 64-character string,
    # and changing even one character gives a completely different one.
    # (Gradle, git and browser caches all use the same trick to detect changes.)
    # encode() turns the text into bytes, because hash functions work on bytes.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    if not DATA_DIR.is_dir():
        raise ConfigurationError(f"Data directory not found: {DATA_DIR}")
    init_schema()

    # {file name: file text} for every markdown file on disk.
    files = {path.name: path.read_text(encoding="utf-8") for path in sorted(DATA_DIR.glob("*.md"))}
    # {file name: hash saved the last time we embedded it}
    stored = get_source_hashes()

    # Three list comprehensions sort the files into groups:
    added = [name for name in files if name not in stored]
    changed = [name for name in files if name in stored and stored[name] != file_hash(files[name])]
    removed = [name for name in stored if name not in files]
    unchanged = len(files) - len(added) - len(changed)

    # "added + changed" joins two lists into one.
    for name in added + changed:
        chunks = chunk_markdown(files[name], source=name)
        if not chunks:
            delete_source(name)  # a file with no content leaves nothing in the table
            continue
        # Only these files go through the embedding model.
        vectors = embed_documents([chunk.text for chunk in chunks])
        replace_source(name, file_hash(files[name]), chunks, vectors)
        print(f"  embedded {name}: {len(chunks)} chunks")

    for name in removed:
        delete_source(name)
        print(f"  removed {name}")

    print(
        f"Done. {len(added)} added, {len(changed)} changed, "
        f"{len(removed)} removed, {unchanged} unchanged."
    )


if __name__ == "__main__":
    main()