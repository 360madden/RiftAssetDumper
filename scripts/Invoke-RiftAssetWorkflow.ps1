<#
.SYNOPSIS
  Optionized RIFT asset discovery workflow helper.

.DESCRIPTION
  Runs focused RiftAssetDumper discovery commands with repeatable smoke/full options.
  Generated reports are written under Exports/ by default, which is intentionally ignored.
#>
[CmdletBinding()]
param(
    [ValidateSet('MeshBindings', 'MeshStreams', 'IndexCandidates', 'StreamEndianness', 'StreamBodies', 'All')]
    [string[]] $Mode = @('MeshBindings'),

    [string] $Root = '',

    [string] $Out = '',

    [string] $Project = '',

    [string] $Solution = '',

    [int] $SmokeMaxTotal = 100,

    [int] $Limit = 100,

    [switch] $Full,

    [switch] $NoSmoke,

    [switch] $SkipBuild,

    [switch] $PrivacyScan
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if ([string]::IsNullOrWhiteSpace($PSScriptRoot)) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { $PSScriptRoot }
$repoRoot = Split-Path $scriptRoot -Parent
if ([string]::IsNullOrWhiteSpace($Root)) { $Root = Join-Path $repoRoot 'Source' }
if ([string]::IsNullOrWhiteSpace($Out)) { $Out = Join-Path $repoRoot 'Exports' }
if ([string]::IsNullOrWhiteSpace($Project)) { $Project = Join-Path $repoRoot 'src\RiftAssetDumper\RiftAssetDumper.csproj' }
if ([string]::IsNullOrWhiteSpace($Solution)) { $Solution = Join-Path $repoRoot 'RiftAssetDumper.slnx' }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

if ($Mode -contains 'All') {
    $Mode = @('MeshBindings', 'MeshStreams', 'IndexCandidates', 'StreamEndianness', 'StreamBodies')
}

$commandMap = @{
    MeshBindings    = @{ Command = 'inventory-nif-mesh-bindings';    Base = 'nif-mesh-binding-inventory' }
    MeshStreams     = @{ Command = 'inventory-nif-mesh-streams';      Base = 'nif-mesh-stream-inventory' }
    IndexCandidates = @{ Command = 'inventory-nif-index-candidates';  Base = 'nif-index-candidate-inventory' }
    StreamEndianness = @{ Command = 'inventory-nif-stream-endianness'; Base = 'nif-stream-endianness-inventory' }
    StreamBodies    = @{ Command = 'inventory-nif-stream-bodies';     Base = 'nif-stream-body-inventory' }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)] [string] $Label,
        [Parameter(Mandatory)] [string[]] $Args
    )

    Write-Host "`n==> $Label" -ForegroundColor Cyan
    Write-Host ('dotnet ' + ($Args -join ' ')) -ForegroundColor DarkGray
    & dotnet @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Label (exit $LASTEXITCODE)"
    }
}

function Get-TopText {
    param([object[]] $Items, [scriptblock] $Formatter, [int] $Take = 5)
    $values = @($Items | Select-Object -First $Take | ForEach-Object { & $Formatter $_ })
    if ($values.Count -eq 0) { return 'none' }
    return ($values -join ' | ')
}

function Show-ReportSummary {
    param([string] $ModeName, [string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Host "No report found: $Path" -ForegroundColor Yellow
        return
    }

    $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    Write-Host "`n--- $ModeName summary: $Path" -ForegroundColor Green
    switch ($ModeName) {
        'MeshBindings' {
            Write-Host "NIF payloads=$($report.NifPayloads) meshBlocks=$($report.MeshBlocks) links=$($report.CandidateLinks) pairMeshes=$($report.PairCompatibleMeshes) pairLinks=$($report.PairCompatibleLinks)"
            Write-Host ('Top roles: ' + (Get-TopText $report.RoleGroups { param($g) "$($g.Role)=$($g.Count)" }))
            Write-Host ('Top pairings: ' + (Get-TopText $report.TopPairings { param($g) "meshSize=$($g.MeshSize) count=$($g.Count) $($g.IndexRole)->$($g.VertexRole) v=$($g.VertexCount) max=$($g.MaxIndexObserved)" }))
        }
        'MeshStreams' {
            Write-Host "NIF payloads=$($report.NifPayloads) meshBlocks=$($report.MeshBlocks) links=$($report.CandidateLinks) ambiguous=$($report.AmbiguousCandidateLinks)"
            Write-Host ('Top offsets: ' + (Get-TopText $report.OffsetGroups { param($g) "@$($g.PayloadOffset)=$($g.Count)" }))
            Write-Host ('Top patterns: ' + (Get-TopText $report.TopPatterns { param($g) "meshSize=$($g.MeshSize) count=$($g.Count)" }))
        }
        'IndexCandidates' {
            Write-Host "NIF payloads=$($report.NifPayloads) streams=$($report.DataStreamBlocks) beLeads=$($report.BigEndianLeadBodies) beTri=$($report.BigEndianTriangleAlignedBodies) stripLess=$($report.TriangleStripLessDegenerateBodies)"
            Write-Host ('Top classes: ' + (Get-TopText $report.ClassGroups { param($g) "$($g.Classification)=$($g.Count)" }))
            Write-Host ('Top BE signatures: ' + (Get-TopText $report.TopBigEndianIndexSignatures { param($g) "payload=$($g.DeclaredPayloadBytes) count=$($g.Count) first16=$($g.PayloadFirst16)" }))
        }
        'StreamEndianness' {
            Write-Host "NIF payloads=$($report.NifPayloads) evenBodies=$($report.EvenLengthBodies)"
            Write-Host ('Top classes: ' + (Get-TopText $report.ClassGroups { param($g) "$($g.Classification)=$($g.Count)" }))
        }
        'StreamBodies' {
            Write-Host "NIF payloads=$($report.NifPayloads) validBodies=$($report.ValidStreamBodies) invalid=$($report.InvalidStreamBodies)"
            Write-Host ('Top sizes: ' + (Get-TopText $report.SizeGroups { param($g) "payload=$($g.DeclaredPayloadBytes) count=$($g.Count)" }))
            Write-Host ('Top signatures: ' + (Get-TopText $report.TopSignatures { param($g) "payload=$($g.DeclaredPayloadBytes) count=$($g.Count) first16=$($g.PayloadFirst16)" }))
        }
    }
}

if (-not $SkipBuild) {
    Invoke-Checked -Label 'build' -Args @('build', $Solution, '--nologo')
}

foreach ($modeName in $Mode) {
    $entry = $commandMap[$modeName]
    $command = [string]$entry.Command
    $base = [string]$entry.Base

    if (-not $NoSmoke) {
        $smokePath = Join-Path $Out "$base-smoke.json"
        Invoke-Checked -Label "$modeName smoke" -Args @('run', '--project', $Project, '--', $command, '--root', $Root, '--max-total', [string]$SmokeMaxTotal, '--out', $smokePath, '--limit', [string]$Limit)
        Show-ReportSummary -ModeName $modeName -Path $smokePath
    }

    if ($Full) {
        $fullPath = Join-Path $Out "$base.json"
        Invoke-Checked -Label "$modeName full" -Args @('run', '--project', $Project, '--', $command, '--root', $Root, '--out', $fullPath, '--limit', [string]$Limit)
        Show-ReportSummary -ModeName $modeName -Path $fullPath
    }
}

if ($PrivacyScan) {
    Write-Host "`n==> privacy scan" -ForegroundColor Cyan
    $hits = git -C $repoRoot grep -n -I "mrkoo\|C:\\Users\\" -- . 2>$null
    $rawHits = @($hits | Where-Object { $_ -and ($_ -notmatch '%USERPROFILE%' -and $_ -notmatch '%USERNAME%' -and $_ -notmatch '<WindowsUser>') })
    if ($rawHits.Count -gt 0) {
        Write-Host 'Potential raw private path/account hits:' -ForegroundColor Red
        $rawHits | Select-Object -First 20
        throw 'Privacy scan failed.'
    }

    Write-Host 'Privacy scan passed: no tracked raw username or non-placeholder C:\Users paths.' -ForegroundColor Green
}

Write-Host "`nWorkflow completed." -ForegroundColor Green
