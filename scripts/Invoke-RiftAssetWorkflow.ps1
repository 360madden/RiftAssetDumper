<#
.SYNOPSIS
  Optionized RIFT asset discovery workflow helper.

.DESCRIPTION
  Runs focused RiftAssetDumper discovery commands with repeatable smoke/full options.
  Generated reports are written under Exports/ by default, which is intentionally ignored.
#>
[CmdletBinding()]
param(
    [ValidateSet('MeshBindings', 'MeshProbe', 'AttributeExtraProbe', 'AttributeExtraSiblingProofGuard', 'AttributeExtraProofGuard', 'MeshStreams', 'IndexCandidates', 'StreamEndianness', 'StreamBodies', 'All')]
    [string[]] $Mode = @('MeshBindings'),

    [string] $Root = '',

    [string] $Out = '',

    [string] $Project = '',

    [string] $Solution = '',

    [int] $SmokeMaxTotal = 100,

    [int] $Limit = 100,

    [string] $Id = '',

    [int] $MeshBlock = -1,

    [int] $ExtraOffset = -1,

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
    AttributeExtraProbe = @{ Command = 'probe-nif-attribute-extra';   Base = 'probe-nif-attribute-extra' }
    AttributeExtraSiblingProofGuard = @{ Command = 'probe-nif-attribute-extra'; Base = 'probe-nif-attribute-extra' }
    AttributeExtraProofGuard = @{ Command = 'inventory-nif-mesh-bindings'; Base = 'nif-mesh-binding-inventory' }
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

function Get-JsonArrayCountOrDash {
    param([object] $Object, [string] $PropertyName)
    $property = $Object.PSObject.Properties[$PropertyName]
    if ($null -eq $property -or $null -eq $property.Value) { return '-' }
    return @($property.Value).Count
}

function Get-RequiredJsonValue {
    param([object] $Object, [string] $PropertyName, [string] $Context)
    $property = $Object.PSObject.Properties[$PropertyName]
    if ($null -eq $property -or $null -eq $property.Value) {
        throw "AttributeExtraProofGuard failed: missing $PropertyName on $Context."
    }

    return $property.Value
}

function Get-RequiredJsonNumber {
    param([object] $Object, [string] $PropertyName, [string] $Context)
    $value = Get-RequiredJsonValue $Object $PropertyName $Context
    try {
        return [Convert]::ToDouble($value, [Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        throw "AttributeExtraProofGuard failed: $PropertyName on $Context is not numeric: $value"
    }
}

function Get-RequiredJsonInteger {
    param([object] $Object, [string] $PropertyName, [string] $Context)
    $value = Get-RequiredJsonNumber $Object $PropertyName $Context
    return [int]$value
}

function Assert-ProofGuardCondition {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) {
        throw "AttributeExtraProofGuard failed: $Message"
    }
}

function Format-VectorSample {
    param([object] $Sample)
    $components = Get-JsonValueOrDash $Sample 'Components'
    $values = if ($components -eq 2) {
        "$(Get-JsonValueOrDash $Sample 'X'),$(Get-JsonValueOrDash $Sample 'Y')"
    }
    else {
        "$(Get-JsonValueOrDash $Sample 'X'),$(Get-JsonValueOrDash $Sample 'Y'),$(Get-JsonValueOrDash $Sample 'Z')"
    }

    $attribute = [string](Get-JsonValueOrDash $Sample 'Attribute')
    $suffix = if ($attribute -eq 'normal') {
        " len=$(Get-JsonValueOrDash $Sample 'VectorLength')"
    }
    else {
        " prev=$(Get-JsonValueOrDash $Sample 'PreviousDistance') next=$(Get-JsonValueOrDash $Sample 'NextDistance')"
    }

    return "v$($Sample.Index)=($values)$suffix"
}

function Format-ProofReviewSummary {
    param([object] $Fitness)
    $property = $Fitness.PSObject.Properties['FirstSegmentProofReview']
    if ($null -eq $property -or $null -eq $property.Value) { return 'proofFlags=- planes=- sign=- parityBreaks=-' }

    $review = $property.Value
    $flagsProperty = $review.PSObject.Properties['ReviewFlags']
    $flags = if ($null -eq $flagsProperty -or $null -eq $flagsProperty.Value) {
        '-'
    }
    else {
        (@($flagsProperty.Value) -join ',')
    }

    $planeProperty = $review.PSObject.Properties['DominantPlaneCounts']
    $planes = if ($null -eq $planeProperty -or $null -eq $planeProperty.Value) {
        '-'
    }
    else {
        Get-TopText @($planeProperty.Value) { param($p) "$($p.Value):$($p.Count)" } 3
    }

    return "proofFlags=$flags planes=$planes sign=+$(Get-JsonValueOrDash $review 'PositiveDominantSignedAreaCount')/-$(Get-JsonValueOrDash $review 'NegativeDominantSignedAreaCount')/0$(Get-JsonValueOrDash $review 'ZeroDominantSignedAreaCount') parityBreaks=$(Get-JsonValueOrDash $review 'NonAlternatingParityTransitionCount')"
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
            $fitnessProperty = $report.PSObject.Properties['TopAttributeExtraMappingFitness']
            if ($null -ne $fitnessProperty -and $null -ne $fitnessProperty.Value) {
                Write-Host ('Top attribute extra mapping fitness: ' + (Get-TopText @($fitnessProperty.Value) { param($g) "meshSize=$($g.MeshSize) v=$($g.VertexCount) extra@$($g.ExtraMeshPayloadOffset) $($g.ExtraRole) count=$($g.Count) prefer=$($g.PreferredMapping) raw=$($g.RawZeroBasedPreferredCount) sub1=$($g.SubtractOnePreferredCount) avgDelta=$(Get-JsonValueOrDash $g 'AverageMedianMaxEdgeDelta') segDelta=$(Get-JsonValueOrDash $g 'AverageSegmentedMedianMaxEdgeDelta') normGap=$(Get-JsonValueOrDash $g 'AverageSegmentedMedianNormalDeltaGap') uvGap=$(Get-JsonValueOrDash $g 'AverageSegmentedMedianUvDeltaGap') areaGap=$(Get-JsonValueOrDash $g 'AverageSegmentedMedianTriangleAreaGap') proofSwitches=$(Get-JsonValueOrDash $g 'AverageRawFirstSegmentDominantPlaneSwitchCount')/$(Get-JsonValueOrDash $g 'AverageSubtractOneFirstSegmentDominantPlaneSwitchCount') signSwitches=$(Get-JsonValueOrDash $g 'AverageRawFirstSegmentDominantSignedAreaSignSwitchCount')/$(Get-JsonValueOrDash $g 'AverageSubtractOneFirstSegmentDominantSignedAreaSignSwitchCount') parityBreaks=$(Get-JsonValueOrDash $g 'AverageRawFirstSegmentNonAlternatingParityTransitionCount')/$(Get-JsonValueOrDash $g 'AverageSubtractOneFirstSegmentNonAlternatingParityTransitionCount') segments=$(Get-JsonValueOrDash $g 'AverageSegmentCount') droppedCross=$(Get-JsonValueOrDash $g 'AverageDroppedCrossSegmentWindowCount') strip=$(Get-JsonValueOrDash $g 'DominantStripStructureHint') bridges=$(Get-JsonValueOrDash $g 'AverageMirroredBridgeCount') sentinels=$(Get-JsonValueOrDash $g 'SentinelRestartValueCountTotal')" }))
            }
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
        'AttributeExtraProbe' {
            Write-Host "version=$($report.NifVersion) mesh=#$($report.MeshBlockIndex) size=$($report.MeshSize) attributeSets=$($report.AttributeSets) extra@$($report.ExtraMeshPayloadOffset) matches=$($report.Matches)"
            foreach ($extra in @($report.ExtraStreams | Select-Object -First 3)) {
                Write-Host "  extra @$($extra.ExtraMeshPayloadOffset)/#$($extra.ExtraBlockIndex) payload=$($extra.ExtraDeclaredPayloadBytes) header=$($extra.HeaderBytes) role=$($extra.Role) fit=$($extra.FitSummary)"
                Write-Host "    first64=$($extra.BodyFirst64)"
                Write-Host ('    top bytes: ' + (Get-TopText $extra.ByteHistogramTop { param($h) "$($h.Hex)x$($h.Count)" } 8))
                $indexProperty = $extra.PSObject.Properties['IndexCompatibility']
                if ($null -ne $indexProperty -and $null -ne $indexProperty.Value) {
                    $index = $indexProperty.Value
                    Write-Host "    index: $($index.CandidateTopology) min=$($index.MinIndex) max=$($index.MaxIndex) distinct=$($index.DistinctIndexCount) withinVertexCount=$($index.MaxIndexWithinVertexCount) maxCoverage=$($index.MaxIndexCoverageRatio) distinctCoverage=$($index.DistinctIndexCoverageRatio) usesZero=$($index.UsesZeroIndex) baseHint=$($index.IndexBaseHint)"
                    Write-Host "    strip: nondegenerate=$($index.TriangleStripNonDegenerateWindowCount)/$($index.TriangleStripWindowCount) stripDegenerate=$($index.TriangleStripDegenerateRatio) fixedTripleDegenerate=$($index.DegenerateTriangleRatio)"
                    $stripStructureProperty = $index.PSObject.Properties['StripStructure']
                    if ($null -ne $stripStructureProperty -and $null -ne $stripStructureProperty.Value) {
                        $strip = $stripStructureProperty.Value
                        Write-Host "    strip structure: $($strip.Hint) degRuns=$($strip.DegenerateRunCount) maxDegRun=$($strip.MaxDegenerateRunLength) nonDegRuns=$($strip.NonDegenerateRunCount) maxNonDegRun=$($strip.MaxNonDegenerateRunLength) adjacentRepeats=$($strip.AdjacentRepeatCount) mirroredBridges=$($strip.MirroredAdjacentRepeatBridgeCount) sentinels=$($strip.SentinelRestartValueCount) zeroValues=$($strip.ZeroIndexValueCount)"
                    }
                    Write-Host ('    mappings: ' + (Get-TopText $index.MappingCandidates { param($m) "$($m.Name) valid=$($m.ValidForVertexCount) offset=$($m.IndexOffset) range=$($m.MappedMinIndex)..$($m.MappedMaxIndex) referenced=$($m.ReferencedVertexCount) missing=$($m.MissingVertexCount) missingSample=$(@($m.MissingVertexSamples | Select-Object -First 4) -join ',')" } 4))
                }
                $positionSamplesProperty = $extra.PSObject.Properties['PositionVertexSamples']
                if ($null -ne $positionSamplesProperty -and $null -ne $positionSamplesProperty.Value) {
                    Write-Host ('    position samples: ' + (Get-TopText @($positionSamplesProperty.Value) { param($s) Format-VectorSample $s } 6))
                }
                $normalSamplesProperty = $extra.PSObject.Properties['NormalVertexSamples']
                if ($null -ne $normalSamplesProperty -and $null -ne $normalSamplesProperty.Value) {
                    Write-Host ('    normal samples: ' + (Get-TopText @($normalSamplesProperty.Value) { param($s) Format-VectorSample $s } 6))
                }
                $uvSamplesProperty = $extra.PSObject.Properties['UvVertexSamples']
                if ($null -ne $uvSamplesProperty -and $null -ne $uvSamplesProperty.Value) {
                    Write-Host ('    uv samples: ' + (Get-TopText @($uvSamplesProperty.Value) { param($s) Format-VectorSample $s } 6))
                }
                $fitnessProperty = $extra.PSObject.Properties['MappingPositionFitness']
                if ($null -ne $fitnessProperty -and $null -ne $fitnessProperty.Value) {
                    $fitnessValues = @($fitnessProperty.Value)
                    if ($fitnessValues.Count -gt 0) {
                        Write-Host ('    position fit: ' + (Get-TopText $fitnessValues { param($f) "$($f.MappingName) finite=$($f.FiniteTriangleWindowCount)/$($f.NonDegenerateTriangleWindowCount) medianMax=$($f.MedianMaxEdge) segs=$(Get-JsonValueOrDash $f 'SegmentCount') segFinite=$(Get-JsonValueOrDash $f 'SegmentedFiniteTriangleWindowCount')/$(Get-JsonValueOrDash $f 'SegmentedTriangleWindowCount') segMedian=$(Get-JsonValueOrDash $f 'SegmentedMedianMaxEdge') normMedian=$(Get-JsonValueOrDash $f 'SegmentedMedianNormalDelta') uvMedian=$(Get-JsonValueOrDash $f 'SegmentedMedianUvDelta') areaMedian=$(Get-JsonValueOrDash $f 'SegmentedMedianTriangleArea') nearZeroArea=$(Get-JsonValueOrDash $f 'SegmentedNearZeroTriangleAreaCount') firstSegTriangles=$(Get-JsonArrayCountOrDash $f 'FirstSegmentTriangles') $(Format-ProofReviewSummary $f) droppedDeg=$(Get-JsonValueOrDash $f 'DroppedDegenerateWindowCount') droppedCross=$(Get-JsonValueOrDash $f 'DroppedCrossSegmentWindowCount')" } 4))
                    }
                }
                Write-Host ('    views: ' + (Get-TopText $extra.GroupedViews { param($v) "$($v.Name) slots=$($v.SlotCount) bytes=$($v.BytesPerSlot) exact=$($v.ExactFit) rem=$($v.RemainderBytes)" } 4))
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

function Invoke-AttributeExtraProofGuard {
    param([Parameter(Mandatory)] [string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "AttributeExtraProofGuard failed: report not found: $Path"
    }

    $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $fitnessProperty = $report.PSObject.Properties['TopAttributeExtraMappingFitness']
    Assert-ProofGuardCondition ($null -ne $fitnessProperty -and $null -ne $fitnessProperty.Value) 'TopAttributeExtraMappingFitness is missing from mesh-binding inventory.'

    $groups = @($fitnessProperty.Value)
    $expectedGroups = @(
        [pscustomobject]@{ VertexCount = 128; MinCount = 2 },
        [pscustomobject]@{ VertexCount = 95; MinCount = 1 },
        [pscustomobject]@{ VertexCount = 80; MinCount = 1 },
        [pscustomobject]@{ VertexCount = 64; MinCount = 1 }
    )

    $results = @()
    $rawPreferredTotal = 0
    $subtractOnePreferredTotal = 0
    $tieTotal = 0

    foreach ($expected in $expectedGroups) {
        $context = "meshSize=297 extra@264 v=$($expected.VertexCount)"
        $matches = @($groups | Where-Object {
            (Get-JsonValueOrDash $_ 'MeshSize') -eq 297 -and
            (Get-JsonValueOrDash $_ 'ExtraMeshPayloadOffset') -eq 264 -and
            (Get-JsonValueOrDash $_ 'ExtraRole') -eq 'index-u16be-strip-lead' -and
            (Get-JsonValueOrDash $_ 'VertexCount') -eq $expected.VertexCount
        })

        Assert-ProofGuardCondition ($matches.Count -eq 1) "$context expected exactly one aggregate group, found $($matches.Count)."
        $group = $matches[0]

        $count = Get-RequiredJsonInteger $group 'Count' $context
        $rawPreferred = Get-RequiredJsonInteger $group 'RawZeroBasedPreferredCount' $context
        $subtractOnePreferred = Get-RequiredJsonInteger $group 'SubtractOnePreferredCount' $context
        $ties = Get-RequiredJsonInteger $group 'TieCount' $context
        $segmentedDelta = Get-RequiredJsonNumber $group 'AverageSegmentedMedianMaxEdgeDelta' $context
        $normalGap = Get-RequiredJsonNumber $group 'AverageSegmentedMedianNormalDeltaGap' $context
        $areaGap = Get-RequiredJsonNumber $group 'AverageSegmentedMedianTriangleAreaGap' $context
        $rawSegmentedEdge = Get-RequiredJsonNumber $group 'AverageRawSegmentedMedianMaxEdge' $context
        $subtractOneSegmentedEdge = Get-RequiredJsonNumber $group 'AverageSubtractOneSegmentedMedianMaxEdge' $context
        $rawArea = Get-RequiredJsonNumber $group 'AverageRawSegmentedMedianTriangleArea' $context
        $subtractOneArea = Get-RequiredJsonNumber $group 'AverageSubtractOneSegmentedMedianTriangleArea' $context
        $droppedCross = Get-RequiredJsonNumber $group 'AverageDroppedCrossSegmentWindowCount' $context
        $rawParityBreaks = Get-RequiredJsonNumber $group 'AverageRawFirstSegmentNonAlternatingParityTransitionCount' $context
        $subtractOneParityBreaks = Get-RequiredJsonNumber $group 'AverageSubtractOneFirstSegmentNonAlternatingParityTransitionCount' $context
        $sentinelRestarts = Get-RequiredJsonInteger $group 'SentinelRestartValueCountTotal' $context
        $preferredMapping = [string](Get-RequiredJsonValue $group 'PreferredMapping' $context)
        $stripHint = [string](Get-RequiredJsonValue $group 'DominantStripStructureHint' $context)

        Assert-ProofGuardCondition ($count -ge $expected.MinCount) "$context count $count is below expected minimum $($expected.MinCount)."
        Assert-ProofGuardCondition ($preferredMapping -eq 'raw-zero-based') "$context preferred mapping changed to $preferredMapping."
        Assert-ProofGuardCondition ($rawPreferred -eq $count) "$context raw preferred count $rawPreferred does not equal group count $count."
        Assert-ProofGuardCondition ($rawPreferred -ge $expected.MinCount) "$context raw preferred count $rawPreferred is below expected minimum $($expected.MinCount)."
        Assert-ProofGuardCondition ($subtractOnePreferred -eq 0) "$context subtract-one preferred count changed to $subtractOnePreferred."
        Assert-ProofGuardCondition ($ties -eq 0) "$context tie count changed to $ties."
        Assert-ProofGuardCondition ($segmentedDelta -gt 0) "$context segmented edge delta is not positive: $segmentedDelta."
        Assert-ProofGuardCondition ($normalGap -gt 0) "$context segmented normal gap is not positive: $normalGap."
        Assert-ProofGuardCondition ($areaGap -gt 0) "$context triangle area gap is not positive: $areaGap."
        Assert-ProofGuardCondition ($rawSegmentedEdge -lt $subtractOneSegmentedEdge) "$context raw segmented edge median is not lower than subtract-one."
        Assert-ProofGuardCondition ($rawArea -lt $subtractOneArea) "$context raw triangle-area median is not lower than subtract-one."
        Assert-ProofGuardCondition ($stripHint -eq 'degenerate-bridge-stitch-candidate') "$context strip structure changed to $stripHint."
        Assert-ProofGuardCondition ($sentinelRestarts -eq 0) "$context sentinel restart total changed to $sentinelRestarts."
        Assert-ProofGuardCondition ($droppedCross -eq 0) "$context dropped cross-segment window average changed to $droppedCross."
        Assert-ProofGuardCondition ($rawParityBreaks -eq 0) "$context raw parity break average changed to $rawParityBreaks."
        Assert-ProofGuardCondition ($subtractOneParityBreaks -eq 0) "$context subtract-one parity break average changed to $subtractOneParityBreaks."

        $rawPreferredTotal += $rawPreferred
        $subtractOnePreferredTotal += $subtractOnePreferred
        $tieTotal += $ties
        $results += [pscustomobject]@{
            VertexCount = $expected.VertexCount
            Count = $count
            RawWins = $rawPreferred
            SubtractOneWins = $subtractOnePreferred
            EdgeDelta = $segmentedDelta
            NormalGap = $normalGap
            AreaGap = $areaGap
            Strip = $stripHint
        }
    }

    Assert-ProofGuardCondition ($rawPreferredTotal -ge 5) "raw preferred total $rawPreferredTotal is below expected minimum 5."
    Assert-ProofGuardCondition ($subtractOnePreferredTotal -eq 0) "subtract-one preferred total changed to $subtractOnePreferredTotal."
    Assert-ProofGuardCondition ($tieTotal -eq 0) "tie total changed to $tieTotal."

    Write-Host "`n--- AttributeExtraProofGuard @264 raw-zero-based proof guard" -ForegroundColor Green
    $results | Sort-Object VertexCount -Descending | Format-Table -AutoSize | Out-Host
    Write-Host "AttributeExtraProofGuard passed: $($expectedGroups.Count) groups, raw preferred total=$rawPreferredTotal, subtract-one total=$subtractOnePreferredTotal, ties=$tieTotal." -ForegroundColor Green
}

function Get-NamedJsonObject {
    param([object[]] $Items, [string] $Name, [string] $Context)
    $matches = @($Items | Where-Object { [string](Get-JsonValueOrDash $_ 'Name') -eq $Name -or [string](Get-JsonValueOrDash $_ 'MappingName') -eq $Name })
    Assert-ProofGuardCondition ($matches.Count -eq 1) "$Context expected exactly one item named $Name, found $($matches.Count)."
    return $matches[0]
}

function Test-JsonArrayEquals {
    param([object[]] $Actual, [object[]] $Expected)
    $actualValues = @($Actual)
    $expectedValues = @($Expected)
    if ($actualValues.Count -ne $expectedValues.Count) { return $false }

    for ($i = 0; $i -lt $actualValues.Count; $i++) {
        if ($actualValues[$i] -ne $expectedValues[$i]) { return $false }
    }

    return $true
}

function Invoke-AttributeExtraSiblingProofGuard {
    param([Parameter(Mandatory)] [string] $Path, [Parameter(Mandatory)] [string] $Id)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "AttributeExtraSiblingProofGuard failed: report not found for ${Id}: $Path"
    }

    $context = "asset=$Id mesh=6 extra@264"
    $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $report 'MeshBlockIndex' $context) -eq 6) "$context mesh block changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $report 'MeshSize' $context) -eq 297) "$context mesh size changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $report 'AttributeSets' $context) -eq 1) "$context attribute-set count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $report 'ExtraMeshPayloadOffset' $context) -eq 264) "$context report extra offset changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $report 'Matches' $context) -eq 1) "$context match count changed."

    $extraStreams = @((Get-RequiredJsonValue $report 'ExtraStreams' $context))
    Assert-ProofGuardCondition ($extraStreams.Count -eq 1) "$context expected one matching extra stream, found $($extraStreams.Count)."
    $extra = $extraStreams[0]

    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $extra 'ExtraMeshPayloadOffset' $context) -eq 264) "$context extra stream offset changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $extra 'ExtraBlockIndex' $context) -eq 15) "$context extra block index changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $extra 'ExtraDeclaredPayloadBytes' $context) -eq 906) "$context extra payload size changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $extra 'HeaderBytes' $context) -eq 29) "$context extra header size changed."
    Assert-ProofGuardCondition ([string](Get-RequiredJsonValue $extra 'Role' $context) -eq 'index-u16be-strip-lead') "$context extra role changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $extra 'VertexCount' $context) -eq 128) "$context vertex count changed."
    Assert-ProofGuardCondition ([string](Get-RequiredJsonValue $extra 'PositionRole' $context) -eq 'position-float3-ror1-lead') "$context position role changed."
    Assert-ProofGuardCondition ([string](Get-RequiredJsonValue $extra 'NormalRole' $context) -eq 'normal-float3-ror1-lead') "$context normal role changed."
    Assert-ProofGuardCondition ([string](Get-RequiredJsonValue $extra 'UvRole' $context) -eq 'uv-float2-ror1-lead') "$context UV role changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $extra 'PositionDeclaredPayloadBytes' $context) -eq 1536) "$context position payload size changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $extra 'NormalDeclaredPayloadBytes' $context) -eq 1536) "$context normal payload size changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $extra 'UvDeclaredPayloadBytes' $context) -eq 1024) "$context UV payload size changed."
    Assert-ProofGuardCondition (([string](Get-RequiredJsonValue $extra 'BodyFirst64' $context)).StartsWith('00010002000200010003000400050006')) "$context index prefix changed."

    $index = Get-RequiredJsonValue $extra 'IndexCompatibility' $context
    Assert-ProofGuardCondition ([string](Get-RequiredJsonValue $index 'CandidateTopology' $context) -eq 'explicit-index-strip-lead') "$context candidate topology changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $index 'PairCount' $context) -eq 453) "$context pair count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $index 'MinIndex' $context) -eq 1) "$context min index changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $index 'MaxIndex' $context) -eq 127) "$context max index changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $index 'DistinctIndexCount' $context) -eq 127) "$context distinct index count changed."
    Assert-ProofGuardCondition ([bool](Get-RequiredJsonValue $index 'MaxIndexWithinVertexCount' $context)) "$context max index no longer fits vertex count."
    Assert-ProofGuardCondition (-not [bool](Get-RequiredJsonValue $index 'UsesZeroIndex' $context)) "$context unexpectedly uses raw zero index."
    Assert-ProofGuardCondition ([string](Get-RequiredJsonValue $index 'IndexBaseHint' $context) -eq 'one-based-or-reserved-zero-ambiguous') "$context index-base hint changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $index 'TriangleStripWindowCount' $context) -eq 451) "$context strip window count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $index 'TriangleStripNonDegenerateWindowCount' $context) -eq 318) "$context non-degenerate strip window count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonNumber $index 'TriangleStripDegenerateRatio' $context) -lt (Get-RequiredJsonNumber $index 'DegenerateTriangleRatio' $context)) "$context strip degeneracy is no longer better than fixed triples."

    $strip = Get-RequiredJsonValue $index 'StripStructure' $context
    Assert-ProofGuardCondition ([string](Get-RequiredJsonValue $strip 'Hint' $context) -eq 'degenerate-bridge-stitch-candidate') "$context strip structure changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $strip 'DegenerateWindowCount' $context) -eq 133) "$context degenerate window count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $strip 'NonDegenerateWindowCount' $context) -eq 318) "$context non-degenerate window count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $strip 'DegenerateRunCount' $context) -eq 77) "$context degenerate run count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $strip 'MaxDegenerateRunLength' $context) -eq 2) "$context max degenerate run length changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $strip 'NonDegenerateRunCount' $context) -eq 77) "$context non-degenerate run count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $strip 'MaxNonDegenerateRunLength' $context) -eq 19) "$context max non-degenerate run length changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $strip 'AdjacentRepeatCount' $context) -eq 56) "$context adjacent repeat count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $strip 'MirroredAdjacentRepeatBridgeCount' $context) -eq 51) "$context mirrored bridge count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $strip 'SentinelRestartValueCount' $context) -eq 0) "$context sentinel restart count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $strip 'ZeroIndexValueCount' $context) -eq 0) "$context zero index value count changed."

    $rawCandidate = Get-NamedJsonObject @((Get-RequiredJsonValue $index 'MappingCandidates' $context)) 'raw-zero-based' $context
    $subtractOneCandidate = Get-NamedJsonObject @((Get-RequiredJsonValue $index 'MappingCandidates' $context)) 'subtract-one' $context
    Assert-ProofGuardCondition ([bool](Get-RequiredJsonValue $rawCandidate 'ValidForVertexCount' $context)) "$context raw-zero-based mapping no longer fits."
    Assert-ProofGuardCondition ([bool](Get-RequiredJsonValue $subtractOneCandidate 'ValidForVertexCount' $context)) "$context subtract-one mapping no longer fits."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $rawCandidate 'MappedMinIndex' $context) -eq 1 -and (Get-RequiredJsonInteger $rawCandidate 'MappedMaxIndex' $context) -eq 127) "$context raw mapped range changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $subtractOneCandidate 'MappedMinIndex' $context) -eq 0 -and (Get-RequiredJsonInteger $subtractOneCandidate 'MappedMaxIndex' $context) -eq 126) "$context subtract-one mapped range changed."
    Assert-ProofGuardCondition (Test-JsonArrayEquals @((Get-RequiredJsonValue $rawCandidate 'MissingVertexSamples' $context)) @(0)) "$context raw missing-vertex sample changed."
    Assert-ProofGuardCondition (Test-JsonArrayEquals @((Get-RequiredJsonValue $subtractOneCandidate 'MissingVertexSamples' $context)) @(127)) "$context subtract-one missing-vertex sample changed."

    $rawFitness = Get-NamedJsonObject @((Get-RequiredJsonValue $extra 'MappingPositionFitness' $context)) 'raw-zero-based' $context
    $subtractOneFitness = Get-NamedJsonObject @((Get-RequiredJsonValue $extra 'MappingPositionFitness' $context)) 'subtract-one' $context
    $rawEdge = Get-RequiredJsonNumber $rawFitness 'SegmentedMedianMaxEdge' $context
    $subtractOneEdge = Get-RequiredJsonNumber $subtractOneFitness 'SegmentedMedianMaxEdge' $context
    $rawNormal = Get-RequiredJsonNumber $rawFitness 'SegmentedMedianNormalDelta' $context
    $subtractOneNormal = Get-RequiredJsonNumber $subtractOneFitness 'SegmentedMedianNormalDelta' $context
    $rawUv = Get-RequiredJsonNumber $rawFitness 'SegmentedMedianUvDelta' $context
    $subtractOneUv = Get-RequiredJsonNumber $subtractOneFitness 'SegmentedMedianUvDelta' $context
    $rawArea = Get-RequiredJsonNumber $rawFitness 'SegmentedMedianTriangleArea' $context
    $subtractOneArea = Get-RequiredJsonNumber $subtractOneFitness 'SegmentedMedianTriangleArea' $context

    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $rawFitness 'SegmentCount' $context) -eq 77) "$context raw segment count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $rawFitness 'SegmentedFiniteTriangleWindowCount' $context) -eq 318) "$context raw segmented finite window count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $rawFitness 'SegmentedTriangleWindowCount' $context) -eq 318) "$context raw segmented window count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $rawFitness 'DroppedDegenerateWindowCount' $context) -eq 133) "$context raw dropped-degenerate count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $rawFitness 'DroppedCrossSegmentWindowCount' $context) -eq 0) "$context raw dropped-cross count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $subtractOneFitness 'SegmentCount' $context) -eq 77) "$context subtract-one segment count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $subtractOneFitness 'SegmentedFiniteTriangleWindowCount' $context) -eq 318) "$context subtract-one segmented finite window count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $subtractOneFitness 'SegmentedTriangleWindowCount' $context) -eq 318) "$context subtract-one segmented window count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $subtractOneFitness 'DroppedDegenerateWindowCount' $context) -eq 133) "$context subtract-one dropped-degenerate count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $subtractOneFitness 'DroppedCrossSegmentWindowCount' $context) -eq 0) "$context subtract-one dropped-cross count changed."
    Assert-ProofGuardCondition ($rawEdge -lt $subtractOneEdge -and ($subtractOneEdge - $rawEdge) -gt 4) "$context raw edge fitness no longer clearly beats subtract-one."
    Assert-ProofGuardCondition ($rawNormal -lt $subtractOneNormal -and ($subtractOneNormal - $rawNormal) -gt 0.3) "$context raw normal fitness no longer clearly beats subtract-one."
    Assert-ProofGuardCondition ($rawUv -le $subtractOneUv) "$context raw UV fitness is worse than subtract-one."
    Assert-ProofGuardCondition ($rawArea -lt $subtractOneArea -and ($subtractOneArea - $rawArea) -gt 10) "$context raw triangle-area fitness no longer clearly beats subtract-one."

    $rawTriangles = @((Get-RequiredJsonValue $rawFitness 'FirstSegmentTriangles' $context))
    $subtractOneTriangles = @((Get-RequiredJsonValue $subtractOneFitness 'FirstSegmentTriangles' $context))
    Assert-ProofGuardCondition ($rawTriangles.Count -eq 24) "$context raw first-segment triangle proof count changed."
    Assert-ProofGuardCondition ($subtractOneTriangles.Count -eq 24) "$context subtract-one first-segment triangle proof count changed."
    $rawFirstTriangle = $rawTriangles[0]
    $subtractOneFirstTriangle = $subtractOneTriangles[0]
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $rawFirstTriangle 'StripWindowIndex' $context) -eq 2 -and (Get-RequiredJsonInteger $rawFirstTriangle 'A' $context) -eq 2 -and (Get-RequiredJsonInteger $rawFirstTriangle 'B' $context) -eq 1 -and (Get-RequiredJsonInteger $rawFirstTriangle 'C' $context) -eq 3) "$context first raw triangle changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $subtractOneFirstTriangle 'StripWindowIndex' $context) -eq 2 -and (Get-RequiredJsonInteger $subtractOneFirstTriangle 'A' $context) -eq 1 -and (Get-RequiredJsonInteger $subtractOneFirstTriangle 'B' $context) -eq 0 -and (Get-RequiredJsonInteger $subtractOneFirstTriangle 'C' $context) -eq 2) "$context first subtract-one triangle changed."
    Assert-ProofGuardCondition ([string](Get-RequiredJsonValue $rawFirstTriangle 'DominantAreaPlane' $context) -eq 'xy' -and (Get-RequiredJsonNumber $rawFirstTriangle 'DominantSignedArea' $context) -gt 0) "$context first raw signed-area proof changed."
    Assert-ProofGuardCondition ([string](Get-RequiredJsonValue $subtractOneFirstTriangle 'DominantAreaPlane' $context) -eq 'xy' -and (Get-RequiredJsonNumber $subtractOneFirstTriangle 'DominantSignedArea' $context) -lt 0) "$context first subtract-one signed-area proof changed."

    $rawReview = Get-RequiredJsonValue $rawFitness 'FirstSegmentProofReview' $context
    $subtractOneReview = Get-RequiredJsonValue $subtractOneFitness 'FirstSegmentProofReview' $context
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $rawReview 'TriangleSampleCount' $context) -eq 24) "$context raw proof-review sample count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $subtractOneReview 'TriangleSampleCount' $context) -eq 24) "$context subtract-one proof-review sample count changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $rawReview 'NonAlternatingParityTransitionCount' $context) -eq 0) "$context raw parity proof changed."
    Assert-ProofGuardCondition ((Get-RequiredJsonInteger $subtractOneReview 'NonAlternatingParityTransitionCount' $context) -eq 0) "$context subtract-one parity proof changed."

    return [pscustomobject]@{
        AssetId = $Id
        RawEdgeMedian = $rawEdge
        SubtractOneEdgeMedian = $subtractOneEdge
        RawNormalMedian = $rawNormal
        SubtractOneNormalMedian = $subtractOneNormal
        RawAreaMedian = $rawArea
        SubtractOneAreaMedian = $subtractOneArea
        Segments = Get-RequiredJsonInteger $rawFitness 'SegmentCount' $context
        MirroredBridges = Get-RequiredJsonInteger $strip 'MirroredAdjacentRepeatBridgeCount' $context
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

    if ($modeName -eq 'AttributeExtraSiblingProofGuard') {
        $expectedSiblingProbes = @(
            [pscustomobject]@{ Id = '6fc01704d4a509d5'; MeshBlock = 6; ExtraOffset = 264 },
            [pscustomobject]@{ Id = 'caa9a88e94ec8db0'; MeshBlock = 6; ExtraOffset = 264 }
        )

        $guardResults = @()
        foreach ($expected in $expectedSiblingProbes) {
            $probePath = Join-Path $Out "$base-$($expected.Id)-mesh$($expected.MeshBlock)-extra$($expected.ExtraOffset).json"
            $probeArgs = @('run', '--project', $Project, '--', $command, '--root', $Root, '--id', $expected.Id, '--mesh-block', [string]$expected.MeshBlock, '--extra-offset', [string]$expected.ExtraOffset, '--out', $probePath)
            Invoke-Checked -Label "$modeName $($expected.Id)" -Args $probeArgs
            Show-ReportSummary -ModeName 'AttributeExtraProbe' -Path $probePath
            $guardResults += Invoke-AttributeExtraSiblingProofGuard -Path $probePath -Id $expected.Id
        }

        Write-Host "`n--- AttributeExtraSiblingProofGuard @264 focused sibling proof guard" -ForegroundColor Green
        $guardResults | Format-Table -AutoSize | Out-Host
        Write-Host "AttributeExtraSiblingProofGuard passed: $($guardResults.Count) focused sibling probes kept the raw-zero-based @264 proof invariants." -ForegroundColor Green
        continue
    }

    if ($modeName -eq 'AttributeExtraProbe') {
        if ([string]::IsNullOrWhiteSpace($Id)) {
            throw '-Mode AttributeExtraProbe requires -Id <16hex>.'
        }

        if ($MeshBlock -lt 0) {
            throw '-Mode AttributeExtraProbe requires -MeshBlock <n>.'
        }

        if ($ExtraOffset -lt 0) {
            throw '-Mode AttributeExtraProbe requires -ExtraOffset <n>.'
        }

        $probePath = Join-Path $Out "$base-$Id-mesh$MeshBlock-extra$ExtraOffset.json"
        $probeArgs = @('run', '--project', $Project, '--', $command, '--root', $Root, '--id', $Id, '--mesh-block', [string]$MeshBlock, '--extra-offset', [string]$ExtraOffset, '--out', $probePath)
        Invoke-Checked -Label "$modeName probe" -Args $probeArgs
        Show-ReportSummary -ModeName $modeName -Path $probePath
        continue
    }

    if ($modeName -eq 'AttributeExtraProofGuard') {
        $guardPath = Join-Path $Out "$base.json"
        $guardLimit = [Math]::Max($Limit, 100)
        Invoke-Checked -Label "$modeName inventory" -Args @('run', '--project', $Project, '--', $command, '--root', $Root, '--out', $guardPath, '--limit', [string]$guardLimit)
        Show-ReportSummary -ModeName 'MeshBindings' -Path $guardPath
        Invoke-AttributeExtraProofGuard -Path $guardPath
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
