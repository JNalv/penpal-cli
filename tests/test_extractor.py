"""Tests for penpal.extractor."""
from pathlib import Path
import pytest
from penpal.extractor import extract_code_blocks


@pytest.fixture
def tmp_out(tmp_path):
    return tmp_path / "extracted"


def _make_block(lang: str, body: str) -> str:
    return f"```{lang}\n{body}\n```"


def test_short_block_not_extracted(tmp_out):
    """Block with fewer than min_lines lines and no hint is left unchanged."""
    block = _make_block("python", "x = 1\ny = 2\n")
    content, written = extract_code_blocks(block, tmp_out, min_lines=20)
    assert written == []
    assert "```python" in content


def test_long_block_extracted_auto_name(tmp_out):
    """Block with enough lines is extracted with an auto-generated filename."""
    body = "\n".join(f"line{i} = {i}" for i in range(25))
    block = _make_block("python", body)
    content, written = extract_code_blocks(block, tmp_out, min_lines=20)
    assert len(written) == 1
    assert written[0].suffix == ".py"
    assert "response_1.py" in written[0].name
    assert "[📎 Saved:" in content
    assert written[0].read_text() == body + "\n"


def test_filename_hint_extracted_regardless_of_length(tmp_out):
    """Block with a filename hint is extracted even if it's short."""
    body = "# filename: config.py\nx = 42\n"
    block = _make_block("python", body)
    content, written = extract_code_blocks(block, tmp_out, min_lines=20)
    assert len(written) == 1
    assert written[0].name == "config.py"
    assert "config.py" in content


def test_output_dir_created_if_missing(tmp_path):
    """output_dir is created if it doesn't exist."""
    out_dir = tmp_path / "deep" / "nested"
    body = "\n".join(f"line{i}" for i in range(25))
    block = _make_block("bash", body)
    _, written = extract_code_blocks(block, out_dir, min_lines=20)
    assert out_dir.exists()
    assert len(written) == 1


def test_multiple_blocks_auto_numbered(tmp_out):
    """Multiple qualifying blocks get sequential auto-names."""
    body = "\n".join(f"line{i}" for i in range(25))
    content = _make_block("python", body) + "\n\n" + _make_block("javascript", body)
    _, written = extract_code_blocks(content, tmp_out, min_lines=20)
    assert len(written) == 2
    names = {p.name for p in written}
    assert "response_1.py" in names
    assert "response_2.js" in names


def test_no_lang_block_ignored(tmp_out):
    """Bare ``` blocks without a language are left unchanged."""
    block = "```\nsome code\n```"
    content, written = extract_code_blocks(block, tmp_out)
    assert written == []
    assert "```" in content
