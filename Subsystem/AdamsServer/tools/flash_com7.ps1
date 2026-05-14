param(
    [string]$Port = "",
    [string]$MonitorPort = "",
    [switch]$Monitor,
    [switch]$SkipErase,
    [switch]$ListPorts,
    [int]$WaitSec = 30
)

$ErrorActionPreference = "Stop"

# Returns COM port names that the OS actually has open (not phantom/disconnected entries).
function Get-AvailablePortNames {
    return [System.IO.Ports.SerialPort]::GetPortNames()
}

function Get-PortNameFromText {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $null }
    $m = [regex]::Match($Text, "\(COM\d+\)")
    if ($m.Success) { return $m.Value.Trim("()") }
    return $null
}

# Classify a port by its friendly name / instance ID.
# Priority for upload: USB-UART > ESP32-CDC > ESP32-serial > Unknown
function Get-PortRole {
    param([string]$FriendlyName, [string]$InstanceId)

    if ($InstanceId -like "USB\VID_303A*") { return "ESP32 USB CDC/JTAG" }

    if ($FriendlyName -like "*CH343*" -or
        $FriendlyName -like "*CH340*" -or
        $FriendlyName -like "*CP210*" -or
        $FriendlyName -like "*USB-Enhanced-SERIAL*" -or
        $FriendlyName -like "*USB-SERIAL*" -or
        $FriendlyName -like "*USB Serial*") {
        return "USB-UART adapter"
    }

    if ($FriendlyName -like "*ESP32*") { return "ESP32 serial" }

    return "Unknown"
}

# Collect all serial ports from PnP, annotate each with IsAvailable.
function Get-SerialPorts {
    $available = Get-AvailablePortNames

    $raw = @()
    try {
        $raw = Get-PnpDevice -Class Ports -ErrorAction Stop |
            Where-Object { $_.FriendlyName -match "\(COM\d+\)" }
    } catch {}

    # Fall back to WMI if PnP returned nothing
    if (-not $raw -or $raw.Count -eq 0) {
        try {
            $raw = Get-CimInstance Win32_PnPEntity -ErrorAction Stop |
                Where-Object { $_.Name -match "\(COM\d+\)" }
        } catch {}
    }

    $ports = $raw | ForEach-Object {
        $name = if ($_.FriendlyName) { $_.FriendlyName } else { $_.Name }
        $iid  = if ($_.InstanceId)   { $_.InstanceId }   else { $_.PNPDeviceID }
        $port = Get-PortNameFromText $name
        if (-not $port) { return }
        [PSCustomObject]@{
            PortName    = $port
            Role        = Get-PortRole -FriendlyName $name -InstanceId $iid
            FriendlyName = $name
            InstanceId  = $iid
            PnpStatus   = $_.Status
            IsAvailable = ($available -contains $port)
        }
    } | Where-Object { $_ -and $_.PortName } | Sort-Object PortName -Unique

    # Also surface any OS-available ports not in PnP (rare, but possible)
    foreach ($p in $available) {
        if ($ports -and ($ports | Where-Object { $_.PortName -eq $p })) { continue }
        $ports += [PSCustomObject]@{
            PortName    = $p
            Role        = "Unknown"
            FriendlyName = "$p (OS-visible, no PnP entry)"
            InstanceId  = ""
            PnpStatus   = "OK"
            IsAvailable = $true
        }
    }

    return @($ports)
}

function Show-PortDiagnostics {
    param([object[]]$Ports)

    Write-Host "Serial ports:"
    if (-not $Ports -or $Ports.Count -eq 0) {
        Write-Host "  None detected." -ForegroundColor Yellow
        return
    }

    foreach ($p in $Ports) {
        $avail = if ($p.IsAvailable) { "[LIVE]   " } else { "[phantom]" }
        $color = if ($p.IsAvailable) { "Green" } else { "DarkGray" }
        Write-Host ("  {0} {1,-5}  {2,-22}  {3}" -f $avail, $p.PortName, $p.Role, $p.FriendlyName) -ForegroundColor $color
    }
    Write-Host ""
}

# Pick the best upload port from available candidates.
# Priority: explicit -Port > available USB-UART > available CDC > available other > unavailable USB-UART
function Resolve-UploadPort {
    param([object[]]$Ports, [string]$RequestedPort)

    if ($RequestedPort) { return $RequestedPort }

    $live = @($Ports | Where-Object { $_.IsAvailable })

    $p = $live | Where-Object { $_.Role -eq "USB-UART adapter" } | Select-Object -First 1
    if ($p) { return $p.PortName }

    $p = $live | Where-Object { $_.Role -eq "ESP32 USB CDC/JTAG" } | Select-Object -First 1
    if ($p) { return $p.PortName }

    $p = $live | Where-Object { $_.Role -eq "ESP32 serial" } | Select-Object -First 1
    if ($p) { return $p.PortName }

    $p = $live | Select-Object -First 1
    if ($p) { return $p.PortName }

    # Last resort: unavailable but known adapter (user may reconnect during retries)
    $p = $Ports | Where-Object { $_.Role -eq "USB-UART adapter" } | Select-Object -First 1
    if ($p) { return $p.PortName }

    return $null
}

function Resolve-MonitorPort {
    param([object[]]$Ports, [string]$RequestedPort, [string]$FallbackPort)

    if ($RequestedPort) { return $RequestedPort }

    $p = $Ports | Where-Object { $_.IsAvailable -and $_.Role -eq "ESP32 USB CDC/JTAG" } | Select-Object -First 1
    if ($p) { return $p.PortName }

    return $FallbackPort
}

# Wait up to $WaitSec seconds for a live upload port to appear (user plugging in ESP).
function Wait-ForUploadPort {
    param([int]$TimeoutSec)

    Write-Host "No live upload port found. Waiting up to ${TimeoutSec}s for ESP32..." -ForegroundColor Yellow
    $deadline = (Get-Date).AddSeconds($TimeoutSec)

    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 1500
        $ports = Get-SerialPorts
        $port  = Resolve-UploadPort -Ports $ports -RequestedPort ""
        if ($port -and ($ports | Where-Object { $_.PortName -eq $port -and $_.IsAvailable })) {
            Write-Host "ESP32 appeared on $port" -ForegroundColor Green
            Write-Host ""
            return $ports
        }
        $remaining = [int]($deadline - (Get-Date)).TotalSeconds
        Write-Host ("  still waiting... {0}s left" -f $remaining) -ForegroundColor DarkGray
    }

    throw "Timed out waiting for upload port. Connect the ESP32 via USB and retry."
}

# ── Main ─────────────────────────────────────────────────────────────────────

$scriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$sketchPath   = Split-Path -Parent $scriptDir
$subsystemDir = Split-Path -Parent $sketchPath
$fqbnBase     = "esp32:esp32:esp32s3:FlashMode=qio,FlashSize=16M,PartitionScheme=custom,PSRAM=opi,CDCOnBoot=cdc"
$uploadFqbn   = if ($SkipErase) { $fqbnBase } else { $fqbnBase + ",EraseFlash=all" }
$partitionsFile = Join-Path $sketchPath "partitions.csv"
$arduinoCli   = Join-Path $scriptDir "arduino-cli.exe"

$ports = Get-SerialPorts
Show-PortDiagnostics -Ports $ports

if ($ListPorts) {
    Write-Host "List-only mode complete."
    return
}

if (-not (Test-Path $arduinoCli)) {
    throw "arduino-cli.exe not found at $arduinoCli"
}

# If no -Port given and no live port found - wait for the device to appear
if (-not $Port) {
    $liveUpload = Resolve-UploadPort -Ports $ports -RequestedPort ""
    $isLive = $liveUpload -and ($ports | Where-Object { $_.PortName -eq $liveUpload -and $_.IsAvailable })
    if (-not $isLive) {
        $ports = Wait-ForUploadPort -TimeoutSec $WaitSec
    }
}

$resolvedUploadPort  = Resolve-UploadPort  -Ports $ports -RequestedPort $Port
$resolvedMonitorPort = Resolve-MonitorPort -Ports $ports -RequestedPort $MonitorPort -FallbackPort $resolvedUploadPort

if (-not $resolvedUploadPort) {
    throw "Could not determine upload port. Use -Port COM<N> to specify it manually."
}

Write-Host "Sketch      : $sketchPath"
Write-Host "Upload port : $resolvedUploadPort"
Write-Host "Monitor port: $resolvedMonitorPort"
Write-Host "FQBN        : $fqbnBase"
Write-Host ""

Push-Location $subsystemDir
try {
    & $arduinoCli compile --fqbn $fqbnBase --build-property "build.partitions=$partitionsFile" $sketchPath
    if ($LASTEXITCODE -ne 0) { throw "Compile failed (exit $LASTEXITCODE)" }

    $uploadSucceeded = $false
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Write-Host "Upload attempt $attempt/3 on $resolvedUploadPort..."
        & $arduinoCli upload -p $resolvedUploadPort --fqbn $uploadFqbn $sketchPath
        if ($LASTEXITCODE -eq 0) {
            $uploadSucceeded = $true
            break
        }
        if ($attempt -lt 3) {
            Write-Host "Upload failed. Waiting 3s before retry..."
            Start-Sleep -Seconds 3
        }
    }

    if (-not $uploadSucceeded) {
        Write-Host ""
        Write-Host "Upload failed after 3 attempts." -ForegroundColor Red
        Write-Host "Typical causes:"
        Write-Host "  1. Port open in another program (Arduino IDE, serial monitor)"
        Write-Host "  2. Port number changed - reconnect and run again"
        Write-Host "  3. Board needs manual BOOT+EN reset sequence"
        throw "Upload failed (exit $LASTEXITCODE)"
    }

    Write-Host ""
    if ($Monitor) {
        Write-Host "Upload succeeded. Opening serial monitor on $resolvedMonitorPort..."
        & $arduinoCli monitor -p $resolvedMonitorPort -c baudrate=115200
    } else {
        Write-Host "Upload succeeded on $resolvedUploadPort." -ForegroundColor Green
        Write-Host "To open monitor:"
        Write-Host ('  powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -Monitor')
    }
}
finally {
    Pop-Location
}
