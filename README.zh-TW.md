[English](README.md) | [繁體中文](README.zh-TW.md)

# pdf-to-epub

把 fixed-layout PDF 轉成適合閱讀器使用、可重新排版的 EPUB 3。

這個工具主要處理已經有可用 text layer 的書籍 PDF。它會保留閱讀順序與圖片；如果 Docling 看得到表格、卻無法重建內容，pipeline 會把原頁面的表格區域裁成 PNG，依 surrounding document order 插回 flow。其他非表格圖片則會轉成壓縮 JPEG，避免 EPUB 比來源 PDF 大上好幾倍。

## 為什麼需要這個工具

PDF 保存的是頁面；e-reader 需要的是能配合螢幕尺寸、字級、邊界與閱讀設定重新排版的內容。

`pdf-to-epub` 先用 Docling 把 PDF 轉成結構化 HTML，再修正常見的抽取問題，最後包成 EPUB 3。它不是把每一頁轉成固定圖片，因此在小尺寸 e-ink 閱讀器、平板與手機上都能 reflow。

## 快速開始

macOS 先安裝 system dependencies：

```bash
brew install uv pandoc
```

直接從 PyPI 執行正式版本：

```bash
uvx pdf-to-epub input.pdf -o output.epub \
  --language zh-TW
```

Apple Silicon 可以直接指定 MPS：

```bash
uvx pdf-to-epub input.pdf \
  -o output.epub \
  --language zh-TW \
  --device mps
```

第一次執行會建立 isolated Python environment，也可能下載 Docling model weights。後續執行會沿用 uv 與 model cache。

### 從 local checkout 執行

```bash
git clone https://github.com/daikeren/pdf-to-epub.git
cd pdf-to-epub
uvx --from . pdf-to-epub input.pdf -o output.epub --language zh-TW
```

## Pipeline 做了什麼

1. Docling 抽取結構化 HTML、JSON 與圖片。
2. Postprocessor 移除中文段落中由 PDF 換行產生的多餘空格。
3. 無法重建的 empty table node 會使用裁切後的 lossless PNG fallback。
4. 其他圖片維持原始尺寸，轉成 baseline JPEG。
5. Pandoc 產生附帶目錄與 reader CSS 的 reflowable EPUB 3。
6. 有設定 EPUBCheck jar 時，最後執行正式格式驗證。

預設 JPEG quality 是 88。在下方 benchmark 中，圖片由 420.67 MiB 的中間 PNG 降到 69.25 MiB，圖片尺寸沒有改變。

## EPUBCheck

EPUBCheck 不是必要 dependency，但建議正式產出時使用。從 [W3C 官方 release](https://github.com/w3c/epubcheck/releases)下載後，傳入 jar 路徑：

```bash
uvx pdf-to-epub input.pdf \
  -o output.epub \
  --language zh-TW \
  --epubcheck-jar /path/to/epubcheck.jar
```

也可以設定 `EPUBCHECK_JAR`。環境中必須能執行 `java`。如果沒有設定 jar，conversion 仍會完成，但結果會明確標示 EPUBCheck skipped。

## 常用選項

```text
--quality 88          圖片 JPEG quality，預設 88
--device auto         Docling device：auto、cpu、mps、cuda
--language auto       自動判斷 zh-CN 或 en；其他語言請明確指定
--ocr                 對掃描 PDF 啟用 OCR；預設關閉
--keep-workdir        保留 HTML、JSON 與圖片中間檔
--work-dir PATH       在指定路徑下建立獨立的 run directory
--epubcheck-jar PATH  透過 Java 執行 EPUBCheck
--overwrite           取代既有 output EPUB
```

完整介面請執行 `pdf-to-epub --help`。

目前 `auto` 只會輸出 `zh-CN` 或 `en`。繁中請傳入 `--language zh-TW`；日文、韓文、法文等其他語言，請明確傳入 `--language ja`、`--language ko` 或 `--language fr`。

## 實測結果

以下是單一文件的實測，不代表所有 PDF 都會得到相同速度或品質。

| | 結果 |
|---|---:|
| 來源 | 1,326 頁、57.35 MiB 中文 PDF |
| 產出 | 69.9 MiB reflowable EPUB 3 |
| 完整時間 | 7 分 04 秒 |
| 圖片 | 609 張最佳化圖片 |
| 表格補救 | 1 張 lossless PNG fallback |
| EPUBCheck | 0 errors、0 warnings |

這次測試使用 Apple Silicon、MPS，以及已經 cache 的 Docling model weights。視覺檢查包含封面、圖文混排章節、補回的表格，以及 PSNR 最低的圖片。這份 benchmark 不能證明所有 PDF 都能逐字、逐版面完全保留。

## 使用邊界

- Pipeline 不會呼叫 generative LLM，也不會把書籍文字送到外部 text API。Docling 的 layout、table 與 optional OCR models 都在本機執行。
- OCR 預設關閉。掃描 PDF 請加上 `--ocr`，但處理時間與結果都會更不穩定。
- Reflow 必然包含版面解讀。如果需求是精確視覺還原或封存，請保留原始 PDF。
- 複雜表格可能維持圖片形式。Fallback 會盡量依 surrounding document order 插入，但不保證原 PDF 的精確頁面座標。
- 目前版本實際驗證的環境是 Apple Silicon macOS。其他平台可以使用 Docling 支援的 device，但不在這次 benchmark 的證據範圍內。

## 開發

```bash
uv sync --extra dev
uv run pytest -q
```

目前測試涵蓋 table-only 文件、圖片最佳化、中文 reflow cleanup、來源檔保護、output overwrite protection、work-directory isolation 與 language detection。

## 授權

[MIT](LICENSE) © 2026 Andy Dai
