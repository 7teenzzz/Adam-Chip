param(
    [string]$Ip = "192.168.0.171",
    [int]$DurationSec = 180,
    [int]$WarmupSec = 30,
    [int]$PollMs = 1000,
    [string]$Scenario = "baseline",
    [switch]$PresetSwitch,
    [string]$PresetA = "qvga",
    [string]$PresetB = "vga",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if ($DurationSec -lt 30) {
    throw "DurationSec must be >= 30"
}
if ($PollMs -lt 200) {
    throw "PollMs must be >= 200"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $projectDir "artifacts"
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$baseUrl = "http://$Ip"
$dashboardUrl = "$baseUrl/api/dashboard"
$statusUrl = "$baseUrl/api/status"
$streamUrl = "http://$Ip`:81/stream?runner=$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
$resetUrl = "$baseUrl/api/video_latency/reset"
$presetUrl = "$baseUrl/api/camera/preset/apply"

if ($Scenario -eq "preset_switch") {
    $PresetSwitch = $true
}

function Invoke-JsonGet([string]$url, [int]$timeoutSec = 5) {
    return Invoke-RestMethod -Uri $url -TimeoutSec $timeoutSec -Method GET
}

function Invoke-JsonPost([string]$url, [object]$body, [int]$timeoutSec = 5) {
    $json = $body | ConvertTo-Json -Compress
    return Invoke-RestMethod -Uri $url -TimeoutSec $timeoutSec -Method POST -ContentType "application/json" -Body $json
}

function Invoke-PlainPost([string]$url, [int]$timeoutSec = 5) {
    return Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec $timeoutSec -Method POST
}

function Get-Stats([double[]]$arr) {
    if (-not $arr -or $arr.Count -eq 0) {
        return [pscustomobject]@{ min = 0; avg = 0; p95 = 0; max = 0 }
    }
    $sorted = $arr | Sort-Object
    $idx = [Math]::Ceiling($sorted.Count * 0.95) - 1
    if ($idx -lt 0) { $idx = 0 }
    if ($idx -ge $sorted.Count) { $idx = $sorted.Count - 1 }
    return [pscustomobject]@{
        min = [Math]::Round(($sorted | Select-Object -First 1), 2)
        avg = [Math]::Round((($arr | Measure-Object -Average).Average), 2)
        p95 = [Math]::Round($sorted[$idx], 2)
        max = [Math]::Round(($sorted | Select-Object -Last 1), 2)
    }
}

Write-Host "Checking device availability at $statusUrl ..."
$null = Invoke-JsonGet -url $statusUrl -timeoutSec 5

Write-Host "Resetting video latency metrics..."
$null = Invoke-PlainPost -url $resetUrl -timeoutSec 5

if ($WarmupSec -gt 0) {
    Write-Host "Warmup for $WarmupSec sec..."
    Start-Sleep -Seconds $WarmupSec
}

if ($Scenario -eq "weak_wifi" -and -not $PresetSwitch) {
    # A practical proxy for poor Wi-Fi in local tests: increase frame size/bitrate pressure.
    $PresetA = "uxga"
    $PresetB = "sxga"
}

if ($PresetSwitch -or $Scenario -eq "weak_wifi") {
    Write-Host "Applying start preset: $PresetA"
    $null = Invoke-JsonPost -url $presetUrl -body @{ preset = $PresetA } -timeoutSec 5
}

$streamJob = Start-Job -ScriptBlock {
    param($url, $durationSec)
    try {
        $request = [System.Net.HttpWebRequest]::Create($url)
        $request.Timeout = 15000
        $request.ReadWriteTimeout = 60000
        $response = $request.GetResponse()
        $stream = $response.GetResponseStream()
        $buffer = New-Object byte[] 8192
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        while ($sw.Elapsed.TotalSeconds -lt ($durationSec + 10)) {
            try {
                $read = $stream.Read($buffer, 0, $buffer.Length)
            } catch [System.Net.WebException] {
                if ($sw.Elapsed.TotalSeconds -ge $durationSec) { break }
                continue
            }
            if ($read -le 0) { break }
        }
        $stream.Close()
        $response.Close()
        return "stream_job_ok"
    } catch {
        return "stream_job_error: $($_.Exception.Message)"
    }
} -ArgumentList $streamUrl, $DurationSec

$rows = New-Object System.Collections.Generic.List[object]
$errors = New-Object System.Collections.Generic.List[string]
$testStart = Get-Date
$presetSwitched = $false

while (((Get-Date) - $testStart).TotalSeconds -lt $DurationSec) {
    $elapsedSec = ((Get-Date) - $testStart).TotalSeconds
    if ($PresetSwitch -and -not $presetSwitched -and $elapsedSec -ge ($DurationSec / 2.0)) {
        try {
            Write-Host "Switching preset in-test: $PresetB"
            $null = Invoke-JsonPost -url $presetUrl -body @{ preset = $PresetB } -timeoutSec 5
            $presetSwitched = $true
        } catch {
            $errors.Add("preset_switch_failed: $($_.Exception.Message)") | Out-Null
        }
    }

    try {
        $d = Invoke-JsonGet -url $dashboardUrl -timeoutSec 5
        $vl = $d.video_latency
        $ctr = if ($vl -and $vl.counters) { $vl.counters } else { $null }

        $rows.Add([pscustomobject]@{
            ts = (Get-Date).ToString("HH:mm:ss")
            elapsed_sec = [Math]::Round($elapsedSec, 2)
            fps = [double]$d.fps
            frame_time_ms = [double]$d.frame_time_ms
            stream_send_time_ms = [double]$d.stream_send_time_ms
            video_e2e_p95_ms = [double]$d.video_e2e_p95_ms
            video_send_payload_p95_ms = [double]$d.video_send_payload_p95_ms
            copy_frame_miss_count = if ($ctr) { [double]$ctr.copy_frame_miss_count } else { 0.0 }
            no_new_frame_poll_count = if ($ctr) { [double]$ctr.no_new_frame_poll_count } else { 0.0 }
            latest_mutex_timeout_count = if ($ctr) { [double]$ctr.latest_mutex_timeout_count } else { 0.0 }
            slow_send_strike_count = if ($ctr) { [double]$ctr.slow_send_strike_count } else { 0.0 }
            buffer_realloc_count = if ($ctr) { [double]$ctr.buffer_realloc_count } else { 0.0 }
            frame_skipped_due_stale = if ($ctr) { [double]$ctr.frame_skipped_due_stale } else { 0.0 }
            last_stream_error = [string]$d.last_stream_error
            video_clients = [double]$d.video_clients
        }) | Out-Null
    } catch {
        $errors.Add($_.Exception.Message) | Out-Null
    }
    Start-Sleep -Milliseconds $PollMs
}

$streamJobOutput = Receive-Job -Job $streamJob -Wait -AutoRemoveJob

$stats = [pscustomobject]@{
    fps = Get-Stats ([double[]]($rows | ForEach-Object { $_.fps }))
    frame_time_ms = Get-Stats ([double[]]($rows | ForEach-Object { $_.frame_time_ms }))
    stream_send_time_ms = Get-Stats ([double[]]($rows | ForEach-Object { $_.stream_send_time_ms }))
    video_e2e_p95_ms = Get-Stats ([double[]]($rows | ForEach-Object { $_.video_e2e_p95_ms }))
    video_send_payload_p95_ms = Get-Stats ([double[]]($rows | ForEach-Object { $_.video_send_payload_p95_ms }))
}

$startRow = if ($rows.Count -gt 0) { $rows[0] } else { $null }
$endRow = if ($rows.Count -gt 0) { $rows[$rows.Count - 1] } else { $null }

function Get-Delta($s, $e, [string]$name) {
    if ($null -eq $s -or $null -eq $e) { return 0 }
    return [double]$e.$name - [double]$s.$name
}

$report = [pscustomobject]@{
    scenario = $Scenario
    notes = if ($Scenario -eq "weak_wifi") { "Use with physically weaker RSSI for full validation; preset raised to increase link pressure." } else { "" }
    preset_switch = [bool]$PresetSwitch
    target_ip = $Ip
    warmup_sec = $WarmupSec
    duration_sec = $DurationSec
    poll_ms = $PollMs
    samples = $rows.Count
    poll_errors = $errors.Count
    stream_job = ($streamJobOutput -join "; ")
    stats = $stats
    counters_delta = [pscustomobject]@{
        copy_frame_miss_count = Get-Delta $startRow $endRow "copy_frame_miss_count"
        no_new_frame_poll_count = Get-Delta $startRow $endRow "no_new_frame_poll_count"
        latest_mutex_timeout_count = Get-Delta $startRow $endRow "latest_mutex_timeout_count"
        slow_send_strike_count = Get-Delta $startRow $endRow "slow_send_strike_count"
        buffer_realloc_count = Get-Delta $startRow $endRow "buffer_realloc_count"
        frame_skipped_due_stale = Get-Delta $startRow $endRow "frame_skipped_due_stale"
    }
    unique_last_stream_error = @($rows | Select-Object -ExpandProperty last_stream_error -Unique)
    errors = @($errors)
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$baseName = "video_test_${Scenario}_${stamp}"
$jsonPath = Join-Path $OutputDir "$baseName.json"
$csvPath = Join-Path $OutputDir "$baseName.csv"

$report | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $jsonPath
$rows | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8

Write-Host "Report JSON: $jsonPath"
Write-Host "Samples CSV: $csvPath"
Write-Output ($report | ConvertTo-Json -Depth 8)
