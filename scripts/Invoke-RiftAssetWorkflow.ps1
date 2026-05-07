<#
.SYNOPSIS
  Optionized RIFT asset discovery workflow helper.

.DESCRIPTION
  Runs focused RiftAssetDumper discovery commands with repeatable smoke/full options.
  Generated reports are written under Exports/ by default, which is intentionally ignored.
#>
[CmdletBinding()]
param(
    [ValidateSet('MeshBindings', 'MeshProbe', 'MeshStreams', 'IndexCandidates', 'StreamEndianness', 'StreamBodies', 'All')]
    [string[]] $Mode = @('MeshBindings'),

    [string] $Root = '',

    [string] $Out = '',

    [string] $Project = '',

    [string] $Solution = '',

    [int] $SmokeMaxTotal = 100,

    [int] $Limit = 100,

    [string] $Id = '',

    [int] $MeshBlock = -1,

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
    MeshProbe       = @{ Command = 'probe-nif-mesh';                  Base = 'probe-nif-mesh' }
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

function Get-JsonValueOrDash {
    param([object] $Object, [string] $PropertyName)
    $property = $Object.PSObject.Properties[$PropertyName]
    if ($null -eq $property -or $null -eq $property.Value) { return '-' }
    return $property.Value
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
            Write-Host ('Top attribute sets: ' + (Get-TopText $report.TopAttributeSets { param($g) "meshSize=$($g.MeshSize) count=$($g.Count) p=$($g.PositionDeclaredPayloadBytes)/n=$($g.NormalDeclaredPayloadBytes)/uv=$($g.UvDeclaredPayloadBytes) v=$($g.VertexCount) topology=$($g.Topology.PrimaryTopology)" }))
            Write-Host ('Top attribute topologies: ' + (Get-TopText $report.TopAttributeTopologies { param($g) "$($g.Topology) v=$($g.VertexCount) count=$($g.Count) list=$(Get-JsonValueOrDash $g 'TriangleListTriangleCount') strip=$(Get-JsonValueOrDash $g 'TriangleStripTriangleCount') quad=$(Get-JsonValueOrDash $g 'QuadListQuadCount')" }))
            Write-Host ('Top attribute extras: ' + (Get-TopText $report.TopAttributeExtraStreams { param($g) "$($g.Topology) v=$($g.VertexCount) extra@$($g.ExtraMeshPayloadOffset) payload=$(Get-JsonValueOrDash $g 'ExtraDeclaredPayloadBytes') $($g.ExtraRole) count=$($g.Count) fit=$($g.FitSummary)" }))
        }
        'MeshProbe' {
            Write-Host "version=$($report.NifVersion) meshes=$($report.MeshBlockCount) emitted=$($report.MeshesEmitted) links=$($report.CandidateLinks) pairings=$($report.Pairings) attributeSets=$($report.AttributeSets)"
            foreach ($mesh in @($report.Meshes | Select-Object -First 3)) {
                Write-Host "Mesh #$($mesh.MeshBlockIndex) size=$($mesh.MeshSize) streams=$($mesh.Streams.Count) pairings=$($mesh.Pairings.Count) attributeSets=$($mesh.AttributeSets.Count) payloadWindows=$($mesh.PayloadWindows.Count)"
                Write-Host ('  roles: ' + (Get-TopText $mesh.Streams { param($s) "@$($s.MeshPayloadOffset)->#$($s.TargetBlockIndex) payload=$($s.DeclaredPayloadBytes) $($s.RoleStats.PrimaryRole) c=$($s.RoleStats.Confidence)" } 8))
                Write-Host ('  pairings: ' + (Get-TopText $mesh.Pairings { param($p) "index@$($p.IndexMeshPayloadOffset)/#$($p.IndexBlockIndex) max=$($p.IndexMax) -> stream@$($p.VertexMeshPayloadOffset)/#$($p.VertexBlockIndex) v=$($p.VertexCount)" } 5))
                Write-Host ('  attributes: ' + (Get-TopText $mesh.AttributeSets { param($a) "p@$($a.PositionMeshPayloadOffset)/#$($a.PositionBlockIndex) n@$($a.NormalMeshPayloadOffset)/#$($a.NormalBlockIndex) uv@$($a.UvMeshPayloadOffset)/#$($a.UvBlockIndex) v=$($a.VertexCount) topology=$($a.Topology.PrimaryTopology) extras=$($a.ExtraStreams.Count)" } 5))
                foreach ($attributeSet in @($mesh.AttributeSets | Select-Object -First 2)) {
                    Write-Host ('  attribute extras: ' + (Get-TopText $attributeSet.ExtraStreams { param($e) "@$($e.MeshPayloadOffset)/#$($e.BlockIndex) payload=$(Get-JsonValueOrDash $e 'DeclaredPayloadBytes') $($e.Role) fit=$($e.FitSummary)" } 5))
                }
                Write-Host ('  payload windows: ' + (Get-TopText $mesh.PayloadWindows { param($w) "@$($w.PayloadOffset) bytes=$($w.ByteLength) $($w.Role) v=$($w.VertexCount)" } 5))
            }
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

    if ($modeName -eq 'MeshProbe') {
        if ([string]::IsNullOrWhiteSpace($Id)) {
            throw '-Mode MeshProbe requires -Id <16hex>.'
        }

        $probePath = Join-Path $Out $(if ($MeshBlock -ge 0) { "$base-$Id-mesh$MeshBlock.json" } else { "$base-$Id.json" })
        $probeArgs = @('run', '--project', $Project, '--', $command, '--root', $Root, '--id', $Id, '--out', $probePath)
        if ($MeshBlock -ge 0) {
            $probeArgs += @('--mesh-block', [string]$MeshBlock)
        }

        Invoke-Checked -Label "$modeName probe" -Args $probeArgs
        Show-ReportSummary -ModeName $modeName -Path $probePath
        continue
    }

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
    $localAccountPattern = 'mr' + 'koo'
    $userProfilePattern = 'C:' + '\\Users\\'
    $hits = @()
    $hits += git -C $repoRoot grep -n -I $localAccountPattern -- . 2>$null
    $hits += git -C $repoRoot grep -n -I $userProfilePattern -- . 2>$null
    $rawHits = @($hits | Where-Object { $_ -and ($_ -notmatch '%USERPROFILE%' -and $_ -notmatch '%USERNAME%' -and $_ -notmatch '<WindowsUser>') })
    if ($rawHits.Count -gt 0) {
        Write-Host 'Potential raw private path/account hits:' -ForegroundColor Red
        $rawHits | Select-Object -First 20
        throw 'Privacy scan failed.'
    }

    Write-Host 'Privacy scan passed: no tracked raw username or non-placeholder C:\Users paths.' -ForegroundColor Green
}

Write-Host "`nWorkflow completed." -ForegroundColor Green
