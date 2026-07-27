from __future__ import annotations

from pathlib import Path

from pdf_to_epub.postprocess import infer_language


def test_infer_language_detects_chinese_and_english(tmp_path: Path) -> None:
    chinese = tmp_path / "chinese.html"
    english = tmp_path / "english.html"
    chinese.write_text("<html><body>這是一本中文書籍內容。</body></html>", encoding="utf-8")
    english.write_text(
        "<html><body>This is an English book with readable prose.</body></html>",
        encoding="utf-8",
    )

    assert infer_language(chinese) == "zh-CN"
    assert infer_language(english) == "en"
