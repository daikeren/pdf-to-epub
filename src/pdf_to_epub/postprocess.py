from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString
from PIL import Image


CJK = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"


@dataclass(frozen=True)
class PostprocessStats:
    table_fallbacks: int
    optimized_images: int
    image_input_bytes: int
    image_output_bytes: int


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def add_empty_table_fallbacks(
    soup: BeautifulSoup, metadata_path: Path, target: Path
) -> int:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    body_refs = [child.get("$ref") for child in metadata["body"]["children"]]
    text_by_ref = {text["self_ref"]: text for text in metadata["texts"]}
    fallback_directory = target.parent / "fallback-assets"
    inserted = 0

    for table_index, table in enumerate(metadata["tables"]):
        if table["data"]["table_cells"]:
            continue

        table_ref = table["self_ref"]
        body_index = body_refs.index(table_ref)
        following_ref = next(
            (ref for ref in body_refs[body_index + 1 :] if ref in text_by_ref), None
        )
        preceding_ref = next(
            (ref for ref in reversed(body_refs[:body_index]) if ref in text_by_ref),
            None,
        )

        anchor = None
        insert_before = False
        if following_ref:
            following_text = compact(text_by_ref[following_ref]["text"])
            anchor = next(
                (
                    element
                    for element in soup.body.find_all(
                        ["h1", "h2", "h3", "h4", "p", "li"]
                    )
                    if compact(element.get_text()) == following_text
                ),
                None,
            )
            insert_before = anchor is not None
        if anchor is None and preceding_ref:
            preceding_text = compact(text_by_ref[preceding_ref]["text"])
            anchor = next(
                (
                    element
                    for element in soup.body.find_all(
                        ["h1", "h2", "h3", "h4", "p", "li"]
                    )
                    if compact(element.get_text()) == preceding_text
                ),
                None,
            )
        provenance = table["prov"][0]
        page_number = provenance["page_no"]
        page = metadata["pages"][str(page_number)]
        page_image_path = Path(page["image"]["uri"])
        fallback_directory.mkdir(parents=True, exist_ok=True)
        fallback_path = (
            fallback_directory / f"table-{table_index:03d}-page-{page_number:04d}.png"
        )

        with Image.open(page_image_path) as page_image:
            page_width = page["size"]["width"]
            page_height = page["size"]["height"]
            scale_x = page_image.width / page_width
            scale_y = page_image.height / page_height
            bbox = provenance["bbox"]
            crop_box = (
                round(bbox["l"] * scale_x),
                round((page_height - bbox["t"]) * scale_y),
                round(bbox["r"] * scale_x),
                round((page_height - bbox["b"]) * scale_y),
            )
            page_image.crop(crop_box).save(fallback_path)

        figure = soup.new_tag("figure")
        figure["class"] = ["table-fallback"]
        image = soup.new_tag("img", src=str(fallback_path.resolve()))
        image["alt"] = f"Original PDF page {page_number} table"
        figure.append(image)
        if anchor is None:
            soup.body.append(figure)
        elif insert_before:
            anchor.insert_before(figure)
        else:
            anchor.insert_after(figure)
        inserted += 1

    return inserted


def optimize_reader_images(
    soup: BeautifulSoup, target: Path, jpeg_quality: int
) -> tuple[int, int, int]:
    output_directory = target.parent / "reader-assets"
    output_directory.mkdir(parents=True, exist_ok=True)
    converted_paths: dict[Path, Path] = {}
    input_bytes = 0
    output_bytes = 0

    for image_index, image_tag in enumerate(soup.find_all("img", src=True)):
        source_path = Path(image_tag["src"]).resolve()
        if image_tag.find_parent("figure", class_="table-fallback") is not None:
            continue

        optimized_path = converted_paths.get(source_path)
        if optimized_path is None:
            optimized_path = output_directory / f"image-{image_index:06d}.jpg"
            with Image.open(source_path) as source_image:
                if source_image.mode in {"RGBA", "LA"}:
                    background = Image.new("RGB", source_image.size, "white")
                    background.paste(source_image, mask=source_image.getchannel("A"))
                    reader_image = background
                else:
                    reader_image = source_image.convert("RGB")
                reader_image.save(
                    optimized_path,
                    format="JPEG",
                    quality=jpeg_quality,
                    optimize=True,
                    progressive=False,
                    subsampling="4:2:0",
                )
            converted_paths[source_path] = optimized_path
            input_bytes += source_path.stat().st_size
            output_bytes += optimized_path.stat().st_size

        image_tag["src"] = str(optimized_path.resolve())

    return len(converted_paths), input_bytes, output_bytes


def clean_reflow_text(soup: BeautifulSoup) -> None:
    for node in list(soup.body.find_all(string=True)):
        if not isinstance(node, NavigableString) or node.parent.name in {
            "style",
            "script",
        }:
            continue
        value = str(node)
        value = re.sub(rf"(?<=[{CJK}])\s+(?=[{CJK}])", "", value)
        value = re.sub(rf"(?<=[{CJK}])\s+(?=[，。！？；：、）】》])", "", value)
        value = re.sub(rf"(?<=[（【《])\s+(?=[{CJK}])", "", value)
        if value != str(node):
            node.replace_with(value)


def infer_language(html_path: Path) -> str:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    letters = [character for character in soup.get_text() if character.isalpha()]
    if not letters:
        return "und"
    cjk_count = sum(bool(re.fullmatch(rf"[{CJK}]", character)) for character in letters)
    return "zh-CN" if cjk_count / len(letters) >= 0.2 else "en"


def prepare_epub_html(
    source: Path,
    target: Path,
    metadata_path: Path,
    jpeg_quality: int,
) -> PostprocessStats:
    source = source.resolve()
    target = target.resolve()
    metadata_path = metadata_path.resolve()
    soup = BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser")

    for image in soup.find_all("img", src=True):
        image_path = Path(image["src"])
        if not image_path.is_absolute():
            image["src"] = str((source.parent / image_path).resolve())

    if soup.find("h1") is None:
        for heading in soup.find_all("h2"):
            heading.name = "h1"

    for page in soup.select("div.page"):
        page.unwrap()

    table_fallbacks = add_empty_table_fallbacks(soup, metadata_path, target)
    optimized_images, input_bytes, output_bytes = optimize_reader_images(
        soup, target, jpeg_quality
    )
    clean_reflow_text(soup)
    target.write_text(str(soup), encoding="utf-8")
    return PostprocessStats(
        table_fallbacks=table_fallbacks,
        optimized_images=optimized_images,
        image_input_bytes=input_bytes,
        image_output_bytes=output_bytes,
    )
