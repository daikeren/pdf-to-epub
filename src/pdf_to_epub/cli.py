from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import PipelineConfig, convert


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-to-epub",
        description="Convert a text-layer PDF into a reader-optimized EPUB 3 book.",
    )
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument(
        "--language",
        default="auto",
        help="EPUB language tag; auto is limited to Chinese-versus-English detection",
    )
    parser.add_argument("--quality", type=int, default=88)
    parser.add_argument(
        "--device", choices=["auto", "cpu", "mps", "cuda"], default="auto"
    )
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument("--epubcheck-jar", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    input_pdf = args.input_pdf.expanduser()
    output_epub = args.output or input_pdf.with_suffix(".epub")
    title = args.title or input_pdf.stem
    try:
        result = convert(
            PipelineConfig(
                input_pdf=input_pdf,
                output_epub=output_epub,
                title=title,
                author=args.author,
                language=args.language,
                quality=args.quality,
                device=args.device,
                ocr=args.ocr,
                work_dir=args.work_dir,
                keep_workdir=args.keep_workdir,
                epubcheck_jar=args.epubcheck_jar,
                overwrite=args.overwrite,
            )
        )
    except (RuntimeError, OSError) as error:
        parser.exit(1, f"error: {error}\n")

    mebibytes = result.output_bytes / 1024 / 1024
    total_seconds = (
        result.docling_seconds
        + result.postprocess_seconds
        + result.packaging_seconds
        + result.validation_seconds
    )
    print(f"output={result.output_epub}")
    print(f"size_mib={mebibytes:.2f}")
    print(f"docling_seconds={result.docling_seconds:.2f}")
    print(f"postprocess_seconds={result.postprocess_seconds:.2f}")
    print(f"packaging_seconds={result.packaging_seconds:.2f}")
    print(f"validation_seconds={result.validation_seconds:.2f}")
    print(f"total_seconds={total_seconds:.2f}")
    print(f"optimized_images={result.postprocess.optimized_images}")
    print(f"table_fallbacks={result.postprocess.table_fallbacks}")
    print(f"epubcheck={result.epubcheck_status}")
    if result.kept_workdir:
        print(f"work_dir={result.work_dir}")


if __name__ == "__main__":
    main()
