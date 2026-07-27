from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup
from PIL import Image

from pdf_to_epub.postprocess import prepare_epub_html


def test_table_only_document_appends_fallback_to_body(tmp_path: Path) -> None:
    page_path = tmp_path / "page.png"
    Image.new("RGB", (100, 100), "white").save(page_path)
    source_html = tmp_path / "source.html"
    source_html.write_text("<html><body></body></html>", encoding="utf-8")
    metadata_path = tmp_path / "source.json"
    metadata_path.write_text(
        json.dumps(
            {
                "body": {"children": [{"$ref": "#/tables/0"}]},
                "texts": [],
                "tables": [
                    {
                        "self_ref": "#/tables/0",
                        "data": {"table_cells": []},
                        "prov": [
                            {
                                "page_no": 1,
                                "bbox": {"l": 5, "t": 95, "r": 95, "b": 5},
                            }
                        ],
                    }
                ],
                "pages": {
                    "1": {
                        "size": {"width": 100, "height": 100},
                        "image": {"uri": str(page_path)},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output.html"

    stats = prepare_epub_html(source_html, output, metadata_path, 88)

    soup = BeautifulSoup(output.read_text(encoding="utf-8"), "html.parser")
    assert stats.table_fallbacks == 1
    assert soup.body.find("figure", class_="table-fallback") is not None
