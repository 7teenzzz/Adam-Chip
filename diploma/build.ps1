# build.ps1 -- Convert diploma Markdown chapters to diploma.docx
# Run from any directory: powershell -File "f:\Adam-Chip\diploma\build.ps1"

$ErrorActionPreference = "Stop"

$PANDOC   = "C:\Users\XVII\AppData\Local\Pandoc\pandoc.exe"
$ROOT     = Split-Path -Parent $MyInvocation.MyCommand.Path
$REF_DOC  = "$ROOT\reference.docx"
$OUTPUT   = "$ROOT\diploma.docx"
$CHAPTERS = "$ROOT\chapters"
$SVG2PNG  = "$ROOT\svg2png.js"

# --- Guard: reference.docx ---
$LOCK = "$ROOT\~`$iploma.docx"
if (Test-Path $LOCK) {
    Write-Host "FAIL: diploma.docx is open in Word. Close it first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $REF_DOC)) {
    Write-Host "FAIL: reference.docx not found. Generate it first:" -ForegroundColor Red
    Write-Host "   python `"$ROOT\make_reference.py`"" -ForegroundColor Yellow
    exit 1
}

# --- Step 1: Convert SVGs to PNGs ---
Write-Host "Step 1: Converting SVG diagrams to PNG ..." -ForegroundColor Cyan
node $SVG2PNG
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: svg2png.js failed, images may be missing in docx" -ForegroundColor Yellow
}

# --- Chapter order (basenames only — Set-Location below sets the working dir) ---
$files = @(
    "ch03_chapter3.md",
    "ch04_conclusion.md"
) | ForEach-Object {
    if (-not (Test-Path (Join-Path $CHAPTERS $_))) {
        Write-Warning "Chapter not found, skipping: $_"
        $null
    } else { $_ }
} | Where-Object { $_ -ne $null }

Write-Host ""
Write-Host "Step 2: Chapters included:" -ForegroundColor Cyan
$files | ForEach-Object { Write-Host "  $_" }

# --- Step 2: Run Pandoc (chapters dir as CWD; forward slashes for named opts) ---
Write-Host ""
Write-Host "Step 3: Converting to $OUTPUT ..." -ForegroundColor Cyan

$ROOT_FWD = $ROOT    -replace '\\','/'
$OUT_FWD  = "$ROOT_FWD/diploma.docx"
$REF_FWD  = "$ROOT_FWD/reference.docx"
$LUA_FWD  = "$ROOT_FWD/svg2png.lua"

# Run Pandoc in a fresh subprocess to avoid any CWD pollution from node/Chrome
$pandocArgs = @(
    "--from",  "markdown+smart+escaped_line_breaks",
    "--to",    "docx",
    "--output",        $OUT_FWD,
    "--reference-doc", $REF_FWD,
    "--lua-filter",    $LUA_FWD,
    "--standalone",
    "--wrap", "none"
) + $files

$proc = Start-Process -FilePath $PANDOC `
    -ArgumentList $pandocArgs `
    -WorkingDirectory $CHAPTERS `
    -NoNewWindow -Wait -PassThru
$global:LASTEXITCODE = $proc.ExitCode

if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: Pandoc exit $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

# --- Step 4: Post-process (tables, captions) ---
Write-Host ""
Write-Host "Step 4: Post-processing $OUTPUT ..." -ForegroundColor Cyan
python "$ROOT\postprocess.py"
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: postprocess.py failed" -ForegroundColor Yellow
}

$size = [math]::Round((Get-Item $OUTPUT).Length / 1KB)
Write-Host ""
Write-Host "OK: diploma.docx -> $OUTPUT  ($size KB)" -ForegroundColor Green
