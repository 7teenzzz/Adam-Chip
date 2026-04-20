param(
    [string]$Port = "",
    [string]$MonitorPort = "",
    [switch]$Monitor,
    [switch]$SkipErase,
    [switch]$ListPorts
)

$ErrorActionPreference = "Stop"

function Get-PortNameFromText {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $null
    }

    $match = [regex]::Match($Text, "\(COM\d+\)")
    if ($match.Success) {
        return $match.Value.Trim("()")
    }

    return $null
}

function Get-PortRole {
    param(
        [string]$FriendlyName,
        [string]$InstanceId
    )

    if ($InstanceId -like "USB\VID_303A*") {
        return "ESP32 USB CDC/JTAG"
    }

    if ($FriendlyName -like "*CH343*" -or
        $FriendlyName -like "*CH340*" -or
        $FriendlyName -like "*CP210*" -or
        $FriendlyName -like "*USB-Enhanced-SERIAL*" -or
        $FriendlyName -like "*USB-SERIAL CH340*") {
        return "USB-UART adapter"
    }

    if ($FriendlyName -like "*ESP32*") {
        return "ESP32 serial"
    }

    return "Unknown"
}

function Get-SerialPorts {
    $ports = @()

    try {
        $ports = Get-PnpDevice -Class Ports -ErrorAction Stop |
            Where-Object { $_.FriendlyName -match "\(COM\d+\)" } |
            ForEach-Object {
                [PSCustomObject]@{
                    PortName     = Get-PortNameFromText $_.FriendlyName
                    Role         = Get-PortRole -FriendlyName $_.FriendlyName -InstanceId $_.InstanceId
                    FriendlyName = $_.FriendlyName
                    InstanceId   = $_.InstanceId
                    Status       = $_.Status
                }
            }
    } catch {
        $ports = @()
    }

    if (-not $ports -or $ports.Count -eq 0) {
        try {
            $ports = Get-CimInstance Win32_PnPEntity -ErrorAction Stop |
                Where-Object { $_.Name -match "\(COM\d+\)" } |
                ForEach-Object {
                    [PSCustomObject]@{
                        PortName     = Get-PortNameFromText $_.Name
                        Role         = Get-PortRole -FriendlyName $_.Name -InstanceId $_.PNPDeviceID
                        FriendlyName = $_.Name
                        InstanceId   = $_.PNPDeviceID
                        Status       = $_.Status
                    }
                }
        } catch {
            $ports = @()
        }
    }

    return @($ports | Where-Object { $_.PortName } | Sort-Object PortName -Unique)
}

function Show-PortDiagnostics {
    param([object[]]$Ports)

    Write-Host "Detected serial ports:"
    if (-not $Ports -or $Ports.Count -eq 0) {
        Write-Host "  No COM ports detected." -ForegroundColor Yellow
        return
    }

    $Ports | Format-Table PortName, Role, FriendlyName, Status -AutoSize
    Write-Host ""

    $uploadCandidate = ($Ports | Where-Object { $_.Role -eq "USB-UART adapter" } | Select-Object -First 1).PortName
    $monitorCandidate = ($Ports | Where-Object { $_.Role -eq "ESP32 USB CDC/JTAG" } | Select-Object -First 1).PortName

    Write-Host "Recommended upload port : $uploadCandidate"
    Write-Host "Recommended monitor port: $monitorCandidate"
    Write-Host ""
}

function Resolve-UploadPort {
    param([object[]]$Ports, [string]$RequestedPort)

    if ($RequestedPort) {
        return $RequestedPort
    }

    $candidate = ($Ports | Where-Object { $_.Role -eq "USB-UART adapter" } | Select-Object -First 1).PortName
    if ($candidate) {
        return $candidate
    }

    return ($Ports | Select-Object -First 1).PortName
}

function Resolve-MonitorPort {
    param([object[]]$Ports, [string]$RequestedPort, [string]$FallbackPort)

    if ($RequestedPort) {
        return $RequestedPort
    }

    $candidate = ($Ports | Where-Object { $_.Role -eq "ESP32 USB CDC/JTAG" } | Select-Object -First 1).PortName
    if ($candidate) {
        return $candidate
    }

    return $FallbackPort
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sketchPath = Split-Path -Parent $scriptDir
$subsystemDir = Split-Path -Parent $sketchPath
$projectRoot = Split-Path -Parent $subsystemDir
$fqbnBase = "esp32:esp32:esp32s3:FlashMode=qio,FlashSize=16M,PartitionScheme=custom,PSRAM=opi,CDCOnBoot=cdc"
$uploadFqbn = if ($SkipErase) { $fqbnBase } else { $fqbnBase + ",EraseFlash=all" }
$partitionsFile = Join-Path $sketchPath "partitions.csv"
$arduinoCli = Join-Path $scriptDir "arduino-cli.exe"
$ports = Get-SerialPorts

Show-PortDiagnostics -Ports $ports

if ($ListPorts) {
    Write-Host "List-only mode complete."
    return
}

if (-not (Test-Path $arduinoCli)) {
    throw "arduino-cli.exe not found at $arduinoCli"
}

$resolvedUploadPort = Resolve-UploadPort -Ports $ports -RequestedPort $Port
if (-not $resolvedUploadPort) {
    throw "No upload COM port found. Run with -ListPorts and reconnect the board."
}

$resolvedMonitorPort = Resolve-MonitorPort -Ports $ports -RequestedPort $MonitorPort -FallbackPort $resolvedUploadPort

Write-Host "Project root: $projectRoot"
Write-Host "Subsystem dir: $subsystemDir"
Write-Host "Sketch path : $sketchPath"
Write-Host "Arduino CLI : $arduinoCli"
Write-Host "Upload port : $resolvedUploadPort"
Write-Host "Monitor port: $resolvedMonitorPort"
Write-Host "FQBN        : $fqbnBase"
Write-Host ""

Push-Location $subsystemDir
try {
    & $arduinoCli compile --fqbn $fqbnBase --build-property "build.partitions=$partitionsFile" $sketchPath
    if ($LASTEXITCODE -ne 0) {
        throw "Compile failed with exit code $LASTEXITCODE"
    }

    $uploadSucceeded = $false
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Write-Host "Upload attempt $attempt/3 on $resolvedUploadPort..."
        & $arduinoCli upload -p $resolvedUploadPort --fqbn $uploadFqbn $sketchPath
        if ($LASTEXITCODE -eq 0) {
            $uploadSucceeded = $true
            break
        }

        if ($attempt -lt 3) {
            Write-Host "Upload failed. Waiting 3 seconds before retry..."
            Start-Sleep -Seconds 3
        }
    }

    if (-not $uploadSucceeded) {
        Write-Host ""
        Write-Host "Upload failed after 3 attempts."
        Write-Host "Typical causes:"
        Write-Host "1. COM port is open in another monitor or Arduino IDE window"
        Write-Host "2. Port number changed after reconnect/reset"
        Write-Host "3. Board needs BOOT/EN manual reset sequence"
        Write-Host ""
        Write-Host "Check ports with:"
        Write-Host "powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -ListPorts"
        throw "Upload failed with exit code $LASTEXITCODE"
    }

    if ($Monitor) {
        Write-Host ""
        Write-Host "Opening serial monitor on $resolvedMonitorPort"
        & $arduinoCli monitor -p $resolvedMonitorPort -c baudrate=115200
    } else {
        Write-Host ""
        Write-Host "Flash completed. To open monitor, run:"
        Write-Host "powershell -ExecutionPolicy Bypass -File .\Subsystem\AdamsServer\tools\flash_com7.ps1 -Monitor"
    }
}
finally {
    Pop-Location
}
