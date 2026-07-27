from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup
from PIL import Image

from pdf_to_epub.postprocess import prepare_epub_html


def test_prepare_epub_html_optimizes_images_and_inserts_table_fallback(
    tmp_path: Path,
) -> None:
    figure_path = tmp_path / "figure.png"
    page_path = tmp_path / "page.png"
    Image.new("RGB", (40, 30), "navy").save(figure_path)
    Image.new("RGB", (100, 100), "white").save(page_path)

    source_html = tmp_path / "source.html"
    source_html.write_text(
        f"""<!doctype html><html><body>
        <h2>第一章</h2>
        <p>中 文內容。Use --help and x--y.</p>
        <figure><img src="{figure_path}"></figure>
        <h2>下一章</h2>
        </body></html>""",
        encoding="utf-8",
    )
    metadata = {
        "body": {
            "children": [
                {"$ref": "#/texts/0"},
                {"$ref": "#/texts/1"},
                {"$ref": "#/pictures/0"},
                {"$ref": "#/tables/0"},
                {"$ref": "#/texts/2"},
            ]
        },
        "texts": [
            {"self_ref": "#/texts/0", "text": "第一章"},
            {"self_ref": "#/texts/1", "text": "中 文內容"},
            {"self_ref": "#/texts/2", "text": "下一章"},
        ],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "data": {"table_cells": []},
                "prov": [
                    {
                        "page_no": 2,
                        "bbox": {"l": 10, "t": 90, "r": 90, "b": 10},
                    }
                ],
            }
        ],
        "pages": {
            "2": {
                "size": {"width": 100, "height": 100},
                "image": {"uri": str(page_path)},
            }
        },
    }
    metadata_path = tmp_path / "source.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    target = tmp_path / "output.html"

    stats = prepare_epub_html(source_html, target, metadata_path, 88)

    soup = BeautifulSoup(target.read_text(encoding="utf-8"), "html.parser")
    assert stats.table_fallbacks == 1
    assert stats.optimized_images == 1
    assert soup.find("h1").get_text() == "第一章"
    assert "中文內容" in soup.get_text()
    assert "Use --help and x--y" in soup.get_text()
    images = soup.find_all("img")
    assert len(images) == 2
    assert Path(images[0]["src"]).suffix == ".jpg"
    assert Path(images[1]["src"]).suffix == ".png"
    assert images[1].find_parent("figure")["class"] == ["table-fallback"]
    with Image.open(images[0]["src"]) as optimized:
        assert optimized.size == (40, 30)
    with Image.open(images[1]["src"]) as fallback:
        assert fallback.size == (80, 80)
