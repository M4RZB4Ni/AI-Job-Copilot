from pathlib import Path

from app.core.exceptions import ConfigurationError
from app.models.chunk import DocumentChunk


def chunk_markdown(markdown: str, source: str) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    # Map of heading level -> title, e.g. {1: "Project: Demo", 2: "Results"}.
    # dict is Python's Map.
    headings: dict[int, str] = {}
    # Section path, starts as the file name without ".md" ("cv.md" -> "cv").
    path = source.rsplit(".", 1)[0]
    lines: list[str] = []  # lines collected under the current heading

    # A function inside a function can read the outer variables (lines, path).
    # It changes "lines" with clear() instead of "lines = []", because assigning
    # would create a new local variable and leave the outer list untouched.
    def save() -> None:
        # In Python, join is a method of the separator: "\n".join(list)
        body = "\n".join(lines).strip()
        if body:  # an empty string counts as False
            # Every chunk starts with its path, so a lone bullet still says
            # which project or role it belongs to.
            text = f"{path}\n\n{body}"
            chunks.append(
                DocumentChunk(
                    source=source,
                    section=path,
                    chunk_index=0,
                    text=text,
                    estimated_tokens=len(text) // 4,  # "//" = integer division (Dart: ~/)
                )
            )
        lines.clear()

    for line in markdown.splitlines():
        if line.startswith("#"):
            save()  # close the previous section BEFORE the heading changes
            title = line.lstrip("#").strip()
            level = len(line) - len(line.lstrip("#"))  # number of leading "#"
            # Dict comprehension: keep only the shallower headings, then add this one
            # (Kotlin: filterKeys).
            headings = {lvl: t for lvl, t in headings.items() if lvl < level}
            headings[level] = title
            # " > ".join(...) glues the titles together, sorted by level.
            path = " > ".join(headings[lvl] for lvl in sorted(headings))
        else:
            lines.append(line)
    save()  # the last section has no heading after it, so save it here
    return chunks


def chunk_directory(data_dir: Path) -> list[DocumentChunk]:
    if not data_dir.is_dir():
        raise ConfigurationError(f"Data directory not found: {data_dir}")
    chunks: list[DocumentChunk] = []
    # glob("*.md") finds every markdown file, sorted() keeps the order stable.
    for file in sorted(data_dir.glob("*.md")):
        chunks.extend(chunk_markdown(file.read_text(encoding="utf-8"), source=file.name))
    return chunks