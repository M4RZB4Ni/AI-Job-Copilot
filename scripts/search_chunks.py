import sys

from app.services.embeddings import embed_query
from app.services.vector_store import search


def main() -> None:
    # sys.argv is the list of words typed on the command line:
    #   python -m scripts.search_chunks "leading a team"  ->  ["<script path>", "leading a team"]
    # [1:] skips the first item (the script itself), and " ".join glues the rest together.
    # "a or b" returns b when a is empty, so with no argument we use a default question.
    question = " ".join(sys.argv[1:]) or "offline-first caching"
    results = search(embed_query(question), limit=8)
    print(f"Question: {question}\n")
    for result in results:
        print(f"{result.score:.3f}  {result.source} | {result.section}")
        # [:150] = the first 150 characters. replace() turns line breaks into spaces.
        print("       " + result.text[:150].replace("\n", " ") + "...")


if __name__ == "__main__":
    main()