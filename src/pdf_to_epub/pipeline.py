from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path

from .postprocess import PostprocessStats, infer_language, prepare_epub_html


@dataclass(frozen=True)
class PipelineConfig:
    input_pdf: Path
    output_epub: Path
    title: str
    author: str | None = None
    language: str = "auto"
    quality: int = 88
    device: str = "auto"
    ocr: bool = False
    work_dir: Path | None = None
    keep_workdir: bool = False
    epubcheck_jar: Path | None = None
    overwrite: bool = False


@dataclass(frozen=True)
class PipelineResult:
    output_epub: Path
    output_bytes: int
    work_dir: Path
    kept_workdir: bool
    docling_seconds: float
    postprocess_seconds: float
    packaging_seconds: float
    validation_seconds: float
    epubcheck_status: str
    postprocess: PostprocessStats


def executable(name: str) -> str:
    sibling = Path(sys.executable).with_name(name)
    if sibling.is_file():
        return str(sibling)
    discovered = shutil.which(name)
    if discovered:
        return discovered
    raise RuntimeError(f"Required executable not found: {name}")


def run(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        executable_name = Path(command[0]).name
        raise RuntimeError(
            f"{executable_name} failed with exit status {error.returncode}"
        ) from None


def only_file(directory: Path, suffix: str) -> Path:
    matches = list(directory.glob(f"*{suffix}"))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one {suffix} file in {directory}, found {len(matches)}"
        )
    return matches[0]


def resolve_epubcheck_jar(explicit: Path | None) -> Path | None:
    if explicit is not None:
        candidate = explicit.expanduser().resolve()
        if not candidate.is_file():
            raise RuntimeError(f"EPUBCheck jar not found: {candidate}")
        return candidate
    environment_value = os.environ.get("EPUBCHECK_JAR")
    if environment_value:
        candidate = Path(environment_value).expanduser().resolve()
        if not candidate.is_file():
            raise RuntimeError(f"EPUBCHECK_JAR does not exist: {candidate}")
        return candidate
    return None


def create_run_directory(base: Path | None) -> tuple[Path, bool]:
    if base is None:
        return Path(tempfile.mkdtemp(prefix="pdf-to-epub-")), True
    resolved_base = base.expanduser().resolve()
    resolved_base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="pdf-to-epub-run-", dir=resolved_base)), False


def publish_epub(generated_epub: Path, output_epub: Path, overwrite: bool) -> None:
    """Publish a completed EPUB without exposing a partial destination file."""
    output_epub.parent.mkdir(parents=True, exist_ok=True)
    descriptor, partial_name = tempfile.mkstemp(
        prefix=f".{output_epub.name}.",
        suffix=".partial",
        dir=output_epub.parent,
    )
    partial_output = Path(partial_name)
    try:
        with os.fdopen(descriptor, "wb") as destination:
            with generated_epub.open("rb") as source:
                shutil.copyfileobj(source, destination)

        if overwrite:
            os.replace(partial_output, output_epub)
            return

        try:
            os.link(partial_output, output_epub)
        except FileExistsError:
            raise RuntimeError(
                f"Output exists; pass --overwrite to replace it: {output_epub}"
            ) from None
        partial_output.unlink()
    finally:
        partial_output.unlink(missing_ok=True)


def convert(config: PipelineConfig) -> PipelineResult:
    input_pdf = config.input_pdf.expanduser().resolve()
    output_epub = config.output_epub.expanduser().resolve()
    if not input_pdf.is_file():
        raise RuntimeError(f"Input PDF not found: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise RuntimeError(f"Input must be a PDF: {input_pdf}")
    if input_pdf == output_epub:
        raise RuntimeError("Input PDF and output EPUB must be different paths")
    if output_epub.suffix.lower() != ".epub":
        raise RuntimeError(f"Output must use the .epub extension: {output_epub}")
    if output_epub.exists() and not config.overwrite:
        raise RuntimeError(f"Output exists; pass --overwrite to replace it: {output_epub}")
    if not 1 <= config.quality <= 100:
        raise RuntimeError("JPEG quality must be between 1 and 100")

    docling_executable = executable("docling")
    pandoc_executable = executable("pandoc")
    epubcheck_jar = resolve_epubcheck_jar(config.epubcheck_jar)
    java_executable = executable("java") if epubcheck_jar is not None else None
    work_dir, temporary_workdir = create_run_directory(config.work_dir)
    docling_output = work_dir / "docling"
    docling_output.mkdir(parents=True, exist_ok=True)
    generated_epub = work_dir / "generated.epub"
    cleaned_html = work_dir / "epub-input.html"
    succeeded = False

    try:
        docling_command = [
            docling_executable,
            "convert",
            str(input_pdf),
            "--to",
            "html",
            "--to",
            "json",
            "--image-export-mode",
            "referenced",
            "--tables",
            "--table-mode",
            "accurate",
            "--device",
            config.device,
            "--page-batch-size",
            "4",
            "--release-native-memory-every-n-pages",
            "64",
            "--output",
            str(docling_output),
        ]
        docling_command.append("--ocr" if config.ocr else "--no-ocr")
        start = time.perf_counter()
        run(docling_command)
        docling_seconds = time.perf_counter() - start

        html_path = only_file(docling_output, ".html")
        json_path = only_file(docling_output, ".json")
        start = time.perf_counter()
        postprocess = prepare_epub_html(
            html_path, cleaned_html, json_path, config.quality
        )
        postprocess_seconds = time.perf_counter() - start

        language = (
            infer_language(cleaned_html)
            if config.language == "auto"
            else config.language
        )
        metadata = [
            f"--metadata=title:{config.title}",
            f"--metadata=lang:{language}",
        ]
        if config.author:
            metadata.append(f"--metadata=author:{config.author}")
        css_resource = files("pdf_to_epub").joinpath("reader.css")
        with as_file(css_resource) as css_path:
            pandoc_command = [
                pandoc_executable,
                str(cleaned_html),
                "--from=html",
                "--to=epub3",
                "--toc",
                "--toc-depth=2",
                "--split-level=1",
                f"--css={css_path}",
                *metadata,
                "-o",
                str(generated_epub),
            ]
            start = time.perf_counter()
            run(pandoc_command)
            packaging_seconds = time.perf_counter() - start

        if epubcheck_jar is None:
            validation_seconds = 0.0
            epubcheck_status = "skipped (no EPUBCheck jar configured)"
        else:
            start = time.perf_counter()
            assert java_executable is not None
            run([java_executable, "-jar", str(epubcheck_jar), str(generated_epub)])
            validation_seconds = time.perf_counter() - start
            epubcheck_status = "passed"

        publish_epub(generated_epub, output_epub, config.overwrite)
        succeeded = True
        return PipelineResult(
            output_epub=output_epub,
            output_bytes=output_epub.stat().st_size,
            work_dir=work_dir,
            kept_workdir=config.keep_workdir or not temporary_workdir,
            docling_seconds=docling_seconds,
            postprocess_seconds=postprocess_seconds,
            packaging_seconds=packaging_seconds,
            validation_seconds=validation_seconds,
            epubcheck_status=epubcheck_status,
            postprocess=postprocess,
        )
    except Exception:
        print(f"work_dir_retained={work_dir}", file=sys.stderr)
        raise
    finally:
        if succeeded and temporary_workdir and not config.keep_workdir:
            shutil.rmtree(work_dir)
