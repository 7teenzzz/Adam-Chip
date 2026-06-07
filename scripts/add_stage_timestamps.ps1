#!/usr/bin/env pwsh
<#
.SYNOPSIS
Add timestamps and metadata to Stage 1 and Stage 2 output files.

.DESCRIPTION
Adds a header block with generation timestamp, source info, and status to all files in:
- diploma/project-analysis/ (Stage 1)
- diploma/project-verification/ (Stage 2)

.PARAMETER Stage
Stage number: 1, 2, or 'all' (default: all)

.PARAMETER Force
Overwrite existing timestamps (default: false, skip if already present)

.EXAMPLE
.\add_stage_timestamps.ps1 -Stage 1
.\add_stage_timestamps.ps1 -Stage all -Force
#>

param(
    [ValidateSet('1', '2', 'all')]
    [string]$Stage = 'all',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$timestamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ'

function Add-Timestamp {
    param(
        [string]$FilePath,
        [string]$StageNum,
        [string]$SourceInfo,
        [switch]$SkipIfExists
    )

    $content = Get-Content -Path $FilePath -Raw

    # Check: does it already have timestamp?
    if ($SkipIfExists -and $content -match '<!--\s*GENERATED:') {
        Write-Host "⏭️  SKIP (already has timestamp): $($FilePath | Split-Path -Leaf)"
        return
    }

    # If old timestamp exists, remove it
    if ($content -match '(?s)<!--\s*GENERATED:.*?-->\s*') {
        $content = $content -replace '(?s)<!--\s*GENERATED:.*?-->\s*', ''
        Write-Host "🗑️  Removed old timestamp from: $($FilePath | Split-Path -Leaf)"
    }

    # Add new header
    $header = @"
<!--
GENERATED: $timestamp
STAGE: $StageNum
SOURCE: $SourceInfo
STATUS: OK complete
RUN: Manual or CI-triggered
NEXT_UPDATE: manual trigger or when source changes
-->

"@

    $newContent = $header + $content
    Set-Content -Path $FilePath -Value $newContent -Encoding UTF8
    Write-Host "✅ Added timestamp: $($FilePath | Split-Path -Leaf)"
}

# Stage 1: diploma/project-analysis/
if ($Stage -match '(1|all)') {
    Write-Host "`n🔄 Processing Stage 1 files..."

    $stage1Files = @(
        @{
            Path = 'diploma/project-analysis/ch01/concepts/subjectivity_framework.md'
            Source = 'diploma/Diploma.md (Chapter 1)'
        },
        @{
            Path = 'diploma/project-analysis/ch02/concepts/case_studies.md'
            Source = 'diploma/Diploma.md (Chapter 2.2-2.3)'
        },
        @{
            Path = 'diploma/project-analysis/ch02/concepts/evaluation_criteria_extracted.md'
            Source = 'diploma/Diploma.md (Chapter 2.1)'
        },
        @{
            Path = 'diploma/project-analysis/ch03/architecture/system_map.md'
            Source = 'diploma/Diploma.md (Chapter 3)'
        },
        @{
            Path = 'diploma/project-analysis/ch03/identity/identity_model.md'
            Source = 'diploma/Diploma.md (Chapter 3.2.3)'
        },
        @{
            Path = 'diploma/project-analysis/ch03/interaction/interaction_model.md'
            Source = 'diploma/Diploma.md (Chapter 3.3.4)'
        },
        @{
            Path = 'diploma/project-analysis/ch03/memory/memory_model.md'
            Source = 'diploma/Diploma.md (Chapter 3.2.4)'
        },
        @{
            Path = 'diploma/project-analysis/ch03/requirements/system_requirements.md'
            Source = 'diploma/Diploma.md (Chapter 3)'
        },
        @{
            Path = 'diploma/project-analysis/ch03/runtime/runtime_model.md'
            Source = 'diploma/Diploma.md (Chapter 3)'
        },
        @{
            Path = 'diploma/project-analysis/synthesis/code_community_labels.md'
            Source = 'graphify-out/GRAPH_REPORT.md'
        },
        @{
            Path = 'diploma/project-analysis/synthesis/criteria_to_code.md'
            Source = 'graphify-out/ (code graph analysis)'
        },
        @{
            Path = 'diploma/project-analysis/synthesis/cross_graph_map.md'
            Source = 'diploma/graphify-out/ + graphify-out/'
        },
        @{
            Path = 'diploma/project-analysis/synthesis/master_concepts.md'
            Source = 'diploma/Diploma.md (synthesis)'
        }
    )

    foreach ($file in $stage1Files) {
        $fullPath = Join-Path 'f:/Adam-Chip' $file.Path
        if (Test-Path $fullPath) {
            Add-Timestamp -FilePath $fullPath -StageNum '1' -SourceInfo $file.Source -SkipIfExists:(-not $Force)
        } else {
            Write-Host "⚠️  NOT FOUND: $fullPath"
        }
    }
}

# Stage 2: diploma/project-verification/
if ($Stage -match '(2|all)') {
    Write-Host "`n🔄 Processing Stage 2 files..."

    $stage2Files = @()

    # by-criterion files
    @(
        @{ Num = 1; Name = 'autonomy' },
        @{ Num = 2; Name = 'agency' },
        @{ Num = 3; Name = 'identity' },
        @{ Num = 4; Name = 'normativity' },
        @{ Num = 5; Name = 'temporal' },
        @{ Num = 6; Name = 'interaction' },
        @{ Num = 7; Name = 'embodiment' },
        @{ Num = 8; Name = 'emergence' }
    ) | ForEach-Object {
        $stage2Files += @{
            Path = "diploma/project-verification/by-criterion/crit_0$($_.Num)_$($_.Name).md"
            Source = "evaluation_criteria.md + graphify (crit-$($_.Num))"
        }
    }

    # by-section files
    @(
        @{ Num = '3.1'; Name = 'concept' },
        @{ Num = '3.2'; Name = 'application' },
        @{ Num = '3.3'; Name = 'installation' },
        @{ Num = '3.4'; Name = 'testing' }
    ) | ForEach-Object {
        $stage2Files += @{
            Path = "diploma/project-verification/by-section/$($_.Num)_$($_.Name).md"
            Source = "project-analysis/ + graphify (Chapter $($_.Num))"
        }
    }

    # Checkpoint and blueprint
    $stage2Files += @{
        Path = 'diploma/project-verification/REVIEW_CHECKPOINT.md'
        Source = 'by-criterion/ (synthesis)'
    }
    $stage2Files += @{
        Path = 'diploma/project-verification/chapter3_materials/final_chapter_blueprint.md'
        Source = 'by-section/ (writing guide)'
    }

    foreach ($file in $stage2Files) {
        $fullPath = Join-Path 'f:/Adam-Chip' $file.Path
        if (Test-Path $fullPath) {
            Add-Timestamp -FilePath $fullPath -StageNum '2' -SourceInfo $file.Source -SkipIfExists:(-not $Force)
        } else {
            Write-Host "⚠️  NOT FOUND: $fullPath"
        }
    }
}

Write-Host "`n✅ Done!"
Write-Host "Summary:"
Write-Host "  - Timestamp: $timestamp"
Write-Host "  - Use -Force to overwrite next time"
