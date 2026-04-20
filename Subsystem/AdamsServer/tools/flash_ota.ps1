param(
    [Parameter(Mandatory = $true)]
    [string]$Host,
    [string]$Token = "",
    [string]$Scheme = "http"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sketchPath = Split-Path -Parent $scriptDir
$subsystemDir = Split-Path -Parent $sketchPath
$fqbn = "esp32:esp32:esp32s3:FlashMode=qio,FlashSize=16M,PartitionScheme=custom,PSRAM=opi,CDCOnBoot=cdc"
$partitionsFile = Join-Path $sketchPath "partitions.csv"
$arduinoCli = Join-Path $scriptDir "arduino-cli.exe"
$outputDir = Join-Path $sketchPath "artifacts\\ota-build"

if (-not (Test-Path $arduinoCli)) {
    throw "arduino-cli.exe not found at $arduinoCli"
}

if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

Write-Host "Sketch path : $sketchPath"
Write-Host "Arduino CLI : $arduinoCli"
Write-Host "Output dir  : $outputDir"
Write-Host "Target host : $Host"
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

$firmwareBin = Get-ChildItem -Path $outputDir -Filter *.bin |
    Where-Object { $_.Name -notlike "*bootloader*" -and $_.Name -notlike "*partitions*" } |
    Sort-Object Length -Descending |
    Select-Object -First 1

if (-not $firmwareBin) {
    throw "Firmware .bin not found in $outputDir"
}

$uri = "${Scheme}://${Host}/api/ota/upload"
$headers = @{}
if ($Token) {
    $headers["X-OTA-Token"] = $Token
}

Write-Host "Uploading firmware: $($firmwareBin.FullName)"
Write-Host "POST $uri"
Write-Host ""

$response = Invoke-WebRequest -Uri $uri -Method Post -InFile $firmwareBin.FullName -ContentType "application/octet-stream" -Headers $headers

Write-Host "HTTP status: $($response.StatusCode)"
Write-Host "Response   : $($response.Content)"
Write-Host ""
Write-Host "If upload succeeded, the ESP32 will reboot into the new OTA slot."
