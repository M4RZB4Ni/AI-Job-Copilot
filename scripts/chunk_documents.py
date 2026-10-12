from app.config import DATA_DIR
from app.services.chunking import chunk_directory


def main() -> None:
    chunks = chunk_directory(DATA_DIR)
    print(f"Data directory: {DATA_DIR}")
    print(f"{len(chunks)} chunks\n")
    for number, chunk in enumerate(chunks, start=1):
        print(
            f"[{number}] {chunk.source} | {chunk.section} | "
            f"part {chunk.chunk_index} | ~{chunk.estimated_tokens} tokens"
        )
        preview = chunk.text[:160].replace("\n", " ")
        print(preview + ("..." if len(chunk.text) > 160 else ""))
        print()
    longest = max((chunk.estimated_tokens for chunk in chunks), default=0)
    print(f"Longest chunk: ~{longest} tokens")


if __name__ == "__main__":
    main()