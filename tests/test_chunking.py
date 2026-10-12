from app.services.chunking import chunk_markdown

SAMPLE = """# Project: Demo

## Actions
- Built a thing.
- Shipped it.

## Results
- Made it faster.
"""


def test_sections_become_chunks_with_full_path():
    chunks = chunk_markdown(SAMPLE, source="demo.md")
    assert [c.section for c in chunks] == ["Project: Demo > Actions", "Project: Demo > Results"]
    assert all(c.source == "demo.md" for c in chunks)
    assert "Built a thing." in chunks[0].text


def test_empty_sections_are_skipped():
    assert chunk_markdown("# Title\n\n## Empty\n", source="x.md") == []