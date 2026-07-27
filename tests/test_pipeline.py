from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pdf_to_epub.pipeline import (
    PipelineConfig,
    convert,
    create_run_directory,
    publish_epub,
    resolve_epubcheck_jar,
    run,
)


def test_pipeline_defaults_are_reader_optimized() -> None:
    config = PipelineConfig(
        input_pdf=Path("book.pdf"),
        output_epub=Path("book.epub"),
        title="Book",
    )
    assert config.quality == 88
    assert config.device == "auto"
    assert config.language == "auto"
    assert config.ocr is False


def test_missing_explicit_epubcheck_jar_fails(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="EPUBCheck jar not found"):
        resolve_epubcheck_jar(tmp_path / "missing.jar")


def test_same_input_and_output_path_is_rejected_without_modifying_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "book.pdf"
    original = b"%PDF-1.7 original"
    source.write_bytes(original)

    with pytest.raises(RuntimeError, match="must be different paths"):
        convert(
            PipelineConfig(
                input_pdf=source,
                output_epub=source,
                title="Book",
                overwrite=True,
            )
        )

    assert source.read_bytes() == original


def test_existing_output_is_preserved_without_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "book.pdf"
    output = tmp_path / "book.epub"
    source.write_bytes(b"%PDF-1.7 source")
    output.write_bytes(b"existing epub")

    with pytest.raises(RuntimeError, match="Output exists"):
        convert(PipelineConfig(input_pdf=source, output_epub=output, title="Book"))

    assert output.read_bytes() == b"existing epub"


def test_user_work_directory_gets_unique_run_children(tmp_path: Path) -> None:
    first, first_is_temporary = create_run_directory(tmp_path)
    second, second_is_temporary = create_run_directory(tmp_path)

    assert first.parent == tmp_path
    assert second.parent == tmp_path
    assert first != second
    assert first_is_temporary is False
    assert second_is_temporary is False
    assert first.name.startswith("pdf-to-epub-run-")
    assert second.name.startswith("pdf-to-epub-run-")


def test_publication_does_not_clobber_output_created_during_conversion(
    tmp_path: Path,
) -> None:
    generated = tmp_path / "generated.epub"
    output = tmp_path / "book.epub"
    generated.write_bytes(b"new epub")
    output.write_bytes(b"other run")

    with pytest.raises(RuntimeError, match="Output exists"):
        publish_epub(generated, output, overwrite=False)

    assert output.read_bytes() == b"other run"
    assert list(tmp_path.glob(".*.partial")) == []


def test_publication_does_not_follow_legacy_partial_symlink(tmp_path: Path) -> None:
    generated = tmp_path / "generated.epub"
    output = tmp_path / "book.epub"
    sentinel = tmp_path / "sentinel"
    legacy_partial = tmp_path / "book.epub.partial"
    generated.write_bytes(b"new epub")
    sentinel.write_bytes(b"keep me")
    legacy_partial.symlink_to(sentinel)

    publish_epub(generated, output, overwrite=False)

    assert output.read_bytes() == b"new epub"
    assert sentinel.read_bytes() == b"keep me"
    assert legacy_partial.is_symlink()


def test_subprocess_failure_is_reported_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(command: list[str], check: bool) -> None:
        raise subprocess.CalledProcessError(3, command)

    monkeypatch.setattr(subprocess, "run", fail)

    with pytest.raises(RuntimeError, match="docling failed with exit status 3"):
        run(["/usr/local/bin/docling", "convert"])
