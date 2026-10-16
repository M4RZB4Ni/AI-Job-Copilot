from app.config import DATA_DIR
from app.services.chunking import chunk_directory
from app.services.embeddings import EMBEDDING_DIM, embed_documents, embed_query

QUERIES = [
    "offline-first caching",
    "leading a team of engineers",
    "payments and biometric security",
    "migrating a legacy codebase",
]


def similarity(a: list[float], b: list[float]) -> float:
    # zip(a, b) walks both lists together: (a[0], b[0]), (a[1], b[1]), ...
    # Multiply each pair and add everything up: that is the dot product.
    # Because the vectors have length 1, it equals cosine similarity:
    # higher means closer in meaning.
    return sum(x * y for x, y in zip(a, b))


def main() -> None:
    chunks = chunk_directory(DATA_DIR)
    if not chunks:
        print(f"No chunks found in {DATA_DIR}")
        return

    vectors = embed_documents([chunk.text for chunk in chunks])
    print(f"{len(chunks)} chunks -> {len(vectors)} vectors of {len(vectors[0])} numbers")
    print(f"Expected dimension: {EMBEDDING_DIM}")
    # round(x, 3) keeps 3 decimals. [:5] is a slice: the first 5 items.
    print("First 5 numbers of the first vector:", [round(x, 3) for x in vectors[0][:5]])

    for query in QUERIES:
        query_vector = embed_query(query)
        # Build (score, chunk) pairs, one per chunk.
        scored = [
            (similarity(query_vector, vector), chunk)
            for vector, chunk in zip(vectors, chunks)
        ]
        # sort() reorders the list in place. key=lambda ... tells it what to sort by.
        # A lambda is an inline anonymous function
        # (Dart: (pair) => pair[0], Kotlin: { it.first }).
        scored.sort(key=lambda pair: pair[0], reverse=True)
        print(f"\nQuery: {query}")
        for score, chunk in scored[:3]:  # the 3 best matches
            # :.3f formats a number with 3 decimals.
            print(f"  {score:.3f}  {chunk.source} | {chunk.section}")


if __name__ == "__main__":
    main()