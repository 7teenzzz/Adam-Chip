param(
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [string]$Token = "",
    [string]$Scheme = "http"
)

$ErrorActionPreference = "Stop"

$scriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$sketchPath    = Split-Path -Parent $scriptDir
$subsystemDir  = Split-Path -Parent $sketchPath
$fqbn          = "esp32:esp32:esp32s3:FlashMode=qio,FlashSize=16M,PartitionScheme=custom,PSRAM=opi,CDCOnBoot=cdc"
$partitionsFile = Join-Path $sketchPath "partitions.csv"
$arduinoCli    = Join-Path $scriptDir "arduino-cli.exe"
$outputDir     = Join-Path $sketchPath "artifacts\ota-build"

if (-not (Test-Path $arduinoCli)) {
    throw "arduino-cli.exe not found at $arduinoCli"
}

if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

Write-Host "Sketch path : $sketchPath"
Write-Host "Arduino CLI : $arduinoCli"
Write-Host "Output dir  : $outputDir"
Write-Host "Target host : $Target"
Write-Host ""

Push-Location $subsystemDir
try {
    & $arduinoCli compile --output-dir $outputDir --fqbn $fqbn --build-property "build.partitions=$partitionsFile" $sketchPath
    if ($LASTEXITCODE -ne 0) {
        throw "Compile failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

# Pick app binary (exclude bootloader, partitions table, merged full-flash image)
$firmwareBin = Get-ChildItem -Path $outputDir -Filter "*.bin" |
    Where-Object { $_.Name -notlike "*bootloader*" -and $_.Name -notlike "*partitions*" -and $_.Name -notlike "*merged*" } |
    Sort-Object Length -Descending |
    Select-Object -First 1

if (-not $firmwareBin) {
    throw "Firmware .bin not found in $outputDir"
}

$uri = "${Scheme}://${Target}/api/ota/upload"

Write-Host "Firmware    : $($firmwareBin.Name) ($($firmwareBin.Length) bytes)"
Write-Host "POST        : $uri"
Write-Host ""

# Use curl: Invoke-WebRequest sends Expect:100-continue which ESP32 httpd rejects.
# --limit-rate 300k paces the upload so ESP32 flash writes keep up with the recv loop.
$curlArgs = @(
    "-X", "POST", $uri,
    "-H", "Content-Type: application/octet-stream",
    "-H", "Expect:",
    "--limit-rate", "300k",
    "--data-binary", "@$($firmwareBin.FullName)",
    "-w", "`nHTTP %{http_code}",
    "--silent", "--show-error"
)
if ($Token) {
    $curlArgs += @("-H", "X-OTA-Token: $Token")
}

$output = & curl.exe @curlArgs 2>&1
Write-Host $output

if ($LASTEXITCODE -ne 0) {
    throw "curl upload failed (exit $LASTEXITCODE)"
}

if (($output -join " ") -notlike "*ota_uploaded_reboot_pending*") {
    throw "Unexpected response from ESP32 - check token or OTA state"
}

Write-Host ""
Write-Host "Upload succeeded. ESP32 will reboot into new firmware in a few seconds." -ForegroundColor Green
