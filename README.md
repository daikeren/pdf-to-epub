[English](README.md) | [繁體中文](README.zh-TW.md)

# pdf-to-epub

Convert fixed-layout PDFs into reader-optimized, reflowable EPUB 3 books.

The tool is built for books that already have a usable text layer. It keeps the
reading order, retains figures, adds image fallbacks for tables Docling detects
but cannot reconstruct, and recompresses detected non-table figures as compact
JPEG files for practical e-reader use.

## Why this exists

A PDF preserves a page. An e-reader needs content that can adapt to its screen,
font size, margins, and reading settings.

`pdf-to-epub` turns the PDF into structured HTML with Docling, repairs a few
common extraction artifacts, then packages the result as EPUB 3. The output is
designed to read well across small e-ink readers, tablets, and phones without
turning every source page into a fixed image.

## Quick start

Install the system dependencies on macOS:

```bash
brew install uv pandoc
```

Run the latest version directly from GitHub:

```bash
uvx --from git+https://github.com/daikeren/pdf-to-epub.git \
  pdf-to-epub input.pdf -o output.epub
```

For Apple Silicon, explicitly select MPS:

```bash
uvx --from git+https://github.com/daikeren/pdf-to-epub.git \
  pdf-to-epub input.pdf \
  -o output.epub \
  --device mps
```

The first run installs an isolated Python environment and may download Docling
model weights. Later runs reuse the uv and model caches.

### Run from a local checkout

```bash
git clone https://github.com/daikeren/pdf-to-epub.git
cd pdf-to-epub
uvx --from . pdf-to-epub input.pdf -o output.epub
```

## What the pipeline does

1. Docling extracts structured HTML and JSON with referenced images.
2. The postprocessor removes PDF line-wrap spaces inside Chinese text.
3. Empty table nodes receive cropped, lossless PNG page fallbacks.
4. Other figures are converted to baseline JPEG without resizing.
5. Pandoc packages the result as reflowable EPUB 3 with navigation and reader CSS.
6. EPUBCheck runs when a jar is configured.

The default JPEG quality is 88. It reduced the image payload in the benchmark
below from 420.67 MiB of intermediate PNG files to 69.25 MiB without changing
image dimensions.

## EPUBCheck

Formal EPUB validation is optional but recommended. Download EPUBCheck from the
[official W3C releases](https://github.com/w3c/epubcheck/releases), then pass the
jar path:

```bash
uvx --from git+https://github.com/daikeren/pdf-to-epub.git \
  pdf-to-epub input.pdf \
  -o output.epub \
  --epubcheck-jar /path/to/epubcheck.jar
```

You can also set `EPUBCHECK_JAR`. Java must be available as `java`. If no jar is
configured, conversion still runs and reports EPUBCheck as skipped.

## Common options

```text
--quality 88          JPEG quality for figures; defaults to 88
--device auto         Docling device: auto, cpu, mps, cuda
--language auto       Detect Chinese or English, or pass an EPUB language tag
--ocr                 Enable OCR for scanned PDFs; off by default
--keep-workdir        Retain HTML, JSON, and image intermediates
--work-dir PATH       Create a unique retained run directory under PATH
--epubcheck-jar PATH  Validate with EPUBCheck through Java
--overwrite           Replace an existing output EPUB
```

Run `pdf-to-epub --help` for the complete interface.

Automatic language detection currently emits either `zh-CN` or `en`. Pass an
explicit tag such as `--language zh-TW`, `--language ja`, `--language ko`, or
`--language fr` for other language variants.

## Observed benchmark

This is one measured conversion, not a general performance guarantee.

| | Result |
|---|---:|
| Source | 1,326-page, 57.35 MiB Chinese PDF |
| Output | 69.9 MiB reflowable EPUB 3 |
| End-to-end time | 7 minutes 4 seconds |
| Figures | 609 optimized images |
| Table recovery | 1 lossless PNG fallback |
| EPUBCheck | 0 errors, 0 warnings |

The run used Apple Silicon with MPS and cached Docling model weights. Visual
checks covered the cover, an illustrated chapter, the recovered table, and the
image with the lowest measured PSNR. The benchmark does not prove that every PDF
will preserve every character or layout decision equally well.

## Boundaries

- The pipeline does not call a generative LLM or send book text to an external
  text API. Docling's layout, table, and optional OCR models run locally.
- OCR is off by default. Use `--ocr` for scanned PDFs, with slower and less
  predictable results.
- Reflow requires interpretation. Keep the original PDF when exact visual or
  archival fidelity matters.
- Complex tables may remain images. The fallback tries to follow the surrounding
  document order, but exact page placement is not guaranteed.
- The current version has been exercised on macOS with Apple Silicon. Other
  platforms are expected to use Docling's supported devices but are not covered
  by this benchmark.

## Development

```bash
uv sync --extra dev
uv run pytest -q
```

The test suite covers table-only documents, image optimization, Chinese reflow
cleanup, input preservation, output overwrite protection, work-directory
isolation, and language detection.

## License

[MIT](LICENSE) © 2026 Andy Dai
