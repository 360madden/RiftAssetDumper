<#
.SYNOPSIS
  Optionized RIFT asset discovery workflow helper.

.DESCRIPTION
  Runs focused RiftAssetDumper discovery commands with repeatable smoke/full options.
  Generated reports are written under Exports/ by default, which is intentionally ignored.
#>
[CmdletBinding()]
param(
    [ValidateSet('AssetSignatures', 'AssetSemanticIndex', 'MeshBindings', 'MeshProbe', 'AttributeExtraProbe', 'AttributeExtraSiblingProofGuard', 'AttributeExtraProofGuard', 'UsageAccessCorrelationGuard', 'ResidualLeadGuard', 'ResidualPositionClassifierReport', 'ResidualPositionClusterProbeReport', 'PositionSourceGapReport', 'PositionSourceSiblingLeadGuard', 'PositionSourceSiblingFamilyReport', 'PositionSourceSiblingProbeReport', 'PositionSourceSiblingRepresentativeProbeReport', 'PositionSourceSiblingSecondaryProbeReport', 'PositionSourceSiblingExtraPositionReport', 'DiscoveryWorkbench', 'GeneratedOutputGuard', 'SemanticHintCrossTab', 'MeshStreams', 'IndexCandidates', 'StreamEndianness', 'StreamBodies', 'All')]
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

    [string] $Type = '',

    [string[]] $SemanticCategory = @(),

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
    AssetSignatures = @{ Command = 'inventory-asset-signatures'; Base = 'asset-signature-inventory' }
    AssetSemanticIndex = @{ Command = 'build-asset-semantic-index'; Base = 'asset-semantic-index' }
    MeshBindings    = @{ Command = 'inventory-nif-mesh-bindings';    Base = 'nif-mesh-binding-inventory' }
    MeshProbe       = @{ Command = 'probe-nif-mesh';                  Base = 'probe-nif-mesh' }
    AttributeExtraProbe = @{ Command = 'probe-nif-attribute-extra';   Base = 'probe-nif-attribute-extra' }
    AttributeExtraSiblingProofGuard = @{ Command = 'probe-nif-attribute-extra'; Base = 'probe-nif-attribute-extra' }
    AttributeExtraProofGuard = @{ Command = 'inventory-nif-mesh-bindings'; Base = 'nif-mesh-binding-inventory' }
    UsageAccessCorrelationGuard = @{ Command = 'inventory-nif-mesh-bindings'; Base = 'nif-mesh-binding-inventory' }
    ResidualLeadGuard = @{ Command = 'inventory-nif-mesh-bindings'; Base = 'nif-mesh-binding-inventory' }
    ResidualPositionClassifierReport = @{ Command = 'inventory-nif-mesh-bindings'; Base = 'nif-mesh-binding-inventory' }
    ResidualPositionClusterProbeReport = @{ Command = ''; Base = '' }
    PositionSourceGapReport = @{ Command = 'inventory-nif-mesh-bindings'; Base = 'nif-mesh-binding-inventory' }
    PositionSourceSiblingLeadGuard = @{ Command = 'inventory-nif-mesh-bindings'; Base = 'nif-mesh-binding-inventory' }
    PositionSourceSiblingFamilyReport = @{ Command = 'inventory-nif-mesh-bindings'; Base = 'nif-mesh-binding-inventory' }
    PositionSourceSiblingProbeReport = @{ Command = 'probe-nif-mesh'; Base = 'probe-nif-mesh' }
    PositionSourceSiblingRepresentativeProbeReport = @{ Command = 'probe-nif-mesh'; Base = 'probe-nif-mesh' }
    PositionSourceSiblingSecondaryProbeReport = @{ Command = 'probe-nif-mesh'; Base = 'probe-nif-mesh' }
    PositionSourceSiblingExtraPositionReport = @{ Command = 'probe-nif-mesh'; Base = 'probe-nif-mesh' }
    DiscoveryWorkbench = @{ Command = ''; Base = '' }
    GeneratedOutputGuard = @{ Command = ''; Base = '' }
    SemanticHintCrossTab = @{ Command = ''; Base = '' }
    MeshStreams     = @{ Command = 'inventory-nif-mesh-streams';      Base = 'nif-mesh-stream-inventory' }
    IndexCandidates = @{ Command = 'inventory-nif-index-candidates';  Base = 'nif-index-candidate-inventory' }
    StreamEndianness = @{ Command = 'inventory-nif-stream-endianness'; Base = 'nif-stream-endianness-inventory' }
    StreamBodies    = @{ Command = 'inventory-nif-stream-bodies';     Base = 'nif-stream-body-inventory' }
}

$semanticCategoryArgs = @()
$typeArgs = @()
if (-not [string]::IsNullOrWhiteSpace($Type)) {
    $typeArgs += @('--type', $Type)
}
foreach ($category in @($SemanticCategory)) {
    if (-not [string]::IsNullOrWhiteSpace($category)) {
        $semanticCategoryArgs += @('--semantic-category', $category)
    }
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

function Get-JsonValueOrNull {
    param([object] $Object, [string] $PropertyName)
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$PropertyName]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Get-JsonDoubleOrNull {
    param([object] $Object, [string] $PropertyName)
    $property = $Object.PSObject.Properties[$PropertyName]
    if ($null -eq $property -or $null -eq $property.Value) { return $null }

    try {
        return [Convert]::ToDouble($property.Value, [Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        return $null
    }
}

function Get-MeasureSumOrZero {
    param([object[]] $Items, [string] $PropertyName)
    $sum = 0.0
    foreach ($item in @($Items)) {
        $value = Get-JsonDoubleOrNull $item $PropertyName
        if ($null -ne $value) {
            $sum += $value
        }
    }

    return $sum
}

function Format-NifUsageAccess {
    param([object] $Object, [string] $UsagePropertyName = 'DataStreamUsage', [string] $AccessPropertyName = 'DataStreamAccess')
    return "usage=$(Get-JsonValueOrDash $Object $UsagePropertyName) access=$(Get-JsonValueOrDash $Object $AccessPropertyName)"
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

function Assert-UsageAccessGuardCondition {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) {
        throw "UsageAccessCorrelationGuard failed: $Message"
    }
}

function Test-GeneratedOutputPath {
    param([string] $Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }

    $normalized = $Path.Replace('\', '/')
    return $normalized -match '^(Source|Extracted|Exports)/' -or
        $normalized -match '(^|/)(bin|obj|__pycache__)/' -or
        $normalized -match '\.pyc$'
}

function Invoke-GeneratedOutputGuard {
    $tracked = @(git -C $repoRoot ls-files)
    if ($LASTEXITCODE -ne 0) {
        throw "GeneratedOutputGuard failed: git ls-files exited with $LASTEXITCODE."
    }

    $staged = @(git -C $repoRoot diff --cached --name-only --diff-filter=ACMR)
    if ($LASTEXITCODE -ne 0) {
        throw "GeneratedOutputGuard failed: git diff --cached exited with $LASTEXITCODE."
    }

    $trackedGenerated = @($tracked | Where-Object { Test-GeneratedOutputPath $_ })
    $stagedGenerated = @($staged | Where-Object { Test-GeneratedOutputPath $_ })
    if ($trackedGenerated.Count -gt 0) {
        Write-Host 'Tracked generated/copy/build output paths:' -ForegroundColor Red
        $trackedGenerated | Select-Object -First 40 | Out-Host
        throw "GeneratedOutputGuard failed: tracked generated/copy/build output paths found ($($trackedGenerated.Count))."
    }

    if ($stagedGenerated.Count -gt 0) {
        Write-Host 'Staged generated/copy/build output paths:' -ForegroundColor Red
        $stagedGenerated | Select-Object -First 40 | Out-Host
        throw "GeneratedOutputGuard failed: staged generated/copy/build output paths found ($($stagedGenerated.Count))."
    }

    Write-Host "`n--- GeneratedOutputGuard" -ForegroundColor Green
    Write-Host "Tracked generated/copy/build output paths: $($trackedGenerated.Count)" -ForegroundColor Green
    Write-Host "Staged generated/copy/build output paths: $($stagedGenerated.Count)" -ForegroundColor Green
    Write-Host 'GeneratedOutputGuard passed: Source/, Extracted/, Exports/, bin/, obj/, __pycache__, and .pyc are not tracked or staged.' -ForegroundColor Green
}

function Get-SemanticHintPrimaryModel {
    param([object] $Entry)
    $names = @($Entry.NameCandidates | Where-Object { [string]$_ -match '\.ma$' } | ForEach-Object { [string]$_ })
    $artNames = @($names | Where-Object { $_ -match '^art/project/' } | Select-Object -First 1)
    if ($artNames.Count -gt 0) { return $artNames[0] }
    if ($names.Count -gt 0) { return $names[0] }
    return '-'
}

function Get-SemanticHintBucket {
    param([string] $Path)
    if ([string]::IsNullOrWhiteSpace($Path) -or $Path -eq '-') { return '-' }

    $normalized = $Path.ToLowerInvariant().Replace('\', '/')
    $normalized = $normalized -replace '^z:/twn/', ''
    $normalized = $normalized -replace '^art/project/', ''
    $parts = @($normalized.Split('/') | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($parts.Count -ge 4) { return ($parts[0..3] -join '/') }
    return ($parts -join '/')
}

function New-SemanticHintEntryRow {
    param([object] $Entry, [string] $Job)
    $model = Get-SemanticHintPrimaryModel -Entry $Entry
    return [pscustomobject]@{
        Job = $Job
        AssetIdPrefix = [string]$Entry.AssetIdPrefix
        ArchiveName = [string]$Entry.ArchiveName
        EntryIndex = [int]$Entry.EntryIndex
        Size = [int]$Entry.UnpackedSize
        Bucket = Get-SemanticHintBucket -Path $model
        PrimaryModel = $model
        TextureCount = @($Entry.NameCandidates | Where-Object { [string]$_ -match '\.dds$' }).Count
        Categories = (@($Entry.SemanticCategories) -join ',')
    }
}

function Format-WorkflowMarkdownCell {
    param([object] $Value)
    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) { return '-' }
    return ([string]$Value).Replace('|', '\|')
}

function Invoke-SemanticHintCrossTab {
    $matrixOutDir = Join-Path $Out 'discovery-matrix\nif-semantic-hints'
    $actorPath = Join-Path $matrixOutDir 'semantic-nif-actor-object.json'
    $mapPath = Join-Path $matrixOutDir 'semantic-nif-map-zone.json'
    $poiPath = Join-Path $matrixOutDir 'semantic-nif-waypoint-poi.json'
    foreach ($requiredPath in @($actorPath, $mapPath, $poiPath)) {
        if (-not (Test-Path -LiteralPath $requiredPath)) {
            throw "SemanticHintCrossTab failed: required matrix output is missing: $requiredPath"
        }
    }

    $actor = Get-Content -LiteralPath $actorPath -Raw | ConvertFrom-Json
    $map = Get-Content -LiteralPath $mapPath -Raw | ConvertFrom-Json
    $poi = Get-Content -LiteralPath $poiPath -Raw | ConvertFrom-Json
    $rows = @()
    $rows += @($actor.Entries | ForEach-Object { New-SemanticHintEntryRow -Entry $_ -Job 'hint:actor-object' })
    $rows += @($map.Entries | ForEach-Object { New-SemanticHintEntryRow -Entry $_ -Job 'hint:map-zone' })
    $actorIds = @($actor.Entries | ForEach-Object { [string]$_.AssetIdPrefix })
    $mapIds = @($map.Entries | ForEach-Object { [string]$_.AssetIdPrefix })
    $overlapIds = @($actorIds | Where-Object { $mapIds -contains $_ } | Sort-Object -Unique)
    $bucketRows = @($rows |
        Group-Object Bucket |
        Sort-Object -Property @{Expression = 'Count'; Descending = $true}, Name |
        ForEach-Object {
            [pscustomobject]@{
                Bucket = $_.Name
                Count = $_.Count
                Jobs = (@($_.Group.Job | Sort-Object -Unique) -join ',')
                SampleIds = (@($_.Group | Select-Object -First 5 | ForEach-Object { $_.AssetIdPrefix }) -join ',')
            }
        })
    $overlapRows = @($rows | Where-Object { $overlapIds -contains $_.AssetIdPrefix } | Sort-Object AssetIdPrefix, Job)
    $jsonPath = Join-Path $matrixOutDir 'nif-semantic-hint-crosstab.json'
    $markdownPath = Join-Path $matrixOutDir 'nif-semantic-hint-crosstab.md'
    $summary = [ordered]@{
        Schema = 'nif-semantic-hint-crosstab/v1'
        CandidateOnly = $true
        SourceDirectory = $matrixOutDir
        ActorObjectEntries = @($actor.Entries).Count
        MapZoneEntries = @($map.Entries).Count
        WaypointPoiEntries = @($poi.Entries).Count
        ActorMapOverlapEntries = $overlapIds.Count
        Buckets = $bucketRows
        OverlapRows = $overlapRows
        Interpretation = 'Static NIF semantic hints only. Use as ranking/search context; do not promote runtime truth or geometry/export readiness.'
    }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $markdown = @(
        '# NIF Semantic Hint Cross-tab',
        '',
        'Hint-only cross-tab from bounded `nif-semantic-hints` matrix output. This is static asset search/ranking context only.',
        '',
        ('Summary: actor/object entries={0}; map-zone entries={1}; waypoint/POI entries={2}; actor/map overlap={3}.' -f @($actor.Entries).Count, @($map.Entries).Count, @($poi.Entries).Count, $overlapIds.Count),
        '',
        '## Buckets',
        '',
        '| Bucket | Count | Jobs | Sample IDs |',
        '|---|---:|---|---|'
    )
    foreach ($bucket in $bucketRows) {
        $markdown += ('| {0} | {1} | {2} | {3} |' -f
            (Format-WorkflowMarkdownCell $bucket.Bucket),
            (Format-WorkflowMarkdownCell $bucket.Count),
            (Format-WorkflowMarkdownCell $bucket.Jobs),
            (Format-WorkflowMarkdownCell $bucket.SampleIds))
    }

    $markdown += @(
        '',
        '## Actor/map overlap',
        '',
        '| ID | Job | Archive | Entry | Size | Bucket | Primary model | Textures |',
        '|---|---|---|---:|---:|---|---|---:|'
    )
    foreach ($row in $overlapRows) {
        $markdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} |' -f
            (Format-WorkflowMarkdownCell $row.AssetIdPrefix),
            (Format-WorkflowMarkdownCell $row.Job),
            (Format-WorkflowMarkdownCell $row.ArchiveName),
            (Format-WorkflowMarkdownCell $row.EntryIndex),
            (Format-WorkflowMarkdownCell $row.Size),
            (Format-WorkflowMarkdownCell $row.Bucket),
            (Format-WorkflowMarkdownCell $row.PrimaryModel),
            (Format-WorkflowMarkdownCell $row.TextureCount))
    }

    $markdown += @(
        '',
        'Interpretation: semantic hints can prioritize offline inspection, but they do not prove runtime identity, geometry roles, or export readiness.'
    )
    Set-Content -LiteralPath $markdownPath -Value $markdown -Encoding UTF8

    Write-Host "`n--- SemanticHintCrossTab" -ForegroundColor Green
    Write-Host ("actor/object entries={0}; map-zone entries={1}; waypoint/POI entries={2}; actor/map overlap={3}" -f @($actor.Entries).Count, @($map.Entries).Count, @($poi.Entries).Count, $overlapIds.Count) -ForegroundColor Green
    Write-Host "SemanticHintCrossTab JSON: $jsonPath" -ForegroundColor Green
    Write-Host "SemanticHintCrossTab markdown: $markdownPath" -ForegroundColor Green
    Write-Host 'SemanticHintCrossTab passed: semantic hints remain candidate-only ranking context.' -ForegroundColor Green
}

function Invoke-DiscoveryWorkbench {
    $workbenchScript = Join-Path $scriptRoot 'discovery_workbench.py'
    if (-not (Test-Path -LiteralPath $workbenchScript)) {
        throw "DiscoveryWorkbench failed: missing helper script $workbenchScript"
    }

    $pythonArgs = @($workbenchScript, '--root', $repoRoot, '--exports', $Out)
    if ($PrivacyScan) {
        $pythonArgs += '--privacy-scan'
    }

    Write-Host "`n--- DiscoveryWorkbench candidate-only ranked workbench" -ForegroundColor Green
    Write-Host ('python ' + ($pythonArgs -join ' ')) -ForegroundColor DarkGray
    & python @pythonArgs
    if ($LASTEXITCODE -ne 0) {
        throw "DiscoveryWorkbench failed: python exited with $LASTEXITCODE."
    }

    $scoreboardPath = Join-Path $Out 'discovery-workbench-scoreboard.json'
    $scoreboardMarkdownPath = Join-Path $Out 'discovery-workbench-scoreboard.md'
    $queuePath = Join-Path $Out 'discovery-next-probe-queue.json'
    $queueMarkdownPath = Join-Path $Out 'discovery-next-probe-queue.md'
    foreach ($requiredPath in @($scoreboardPath, $scoreboardMarkdownPath, $queuePath, $queueMarkdownPath)) {
        if (-not (Test-Path -LiteralPath $requiredPath)) {
            throw "DiscoveryWorkbench failed: expected output missing: $requiredPath"
        }
    }

    $scoreboard = Get-Content -LiteralPath $scoreboardPath -Raw | ConvertFrom-Json
    if ($scoreboard.CandidateOnly -ne $true) {
        throw 'DiscoveryWorkbench failed: scoreboard CandidateOnly flag is not true.'
    }

    $candidates = @($scoreboard.Candidates)
    $nonCandidateRows = @($candidates | Where-Object { $_.CandidateOnly -ne $true })
    if ($nonCandidateRows.Count -gt 0) {
        throw "DiscoveryWorkbench failed: non-candidate rows found ($($nonCandidateRows.Count))."
    }

    $crossChecks = @($scoreboard.CrossChecks)
    $nonCandidateChecks = @($crossChecks | Where-Object { $_.CandidateOnly -ne $true })
    if ($nonCandidateChecks.Count -gt 0) {
        throw "DiscoveryWorkbench failed: non-candidate cross-check rows found ($($nonCandidateChecks.Count))."
    }

    $top = $candidates | Sort-Object -Property Rank | Select-Object -First 1
    if ($null -ne $top) {
        Write-Host ("Top candidate: rank={0}; score={1}; id={2}; title={3}" -f $top.Rank, $top.Score, $top.CandidateId, $top.Title) -ForegroundColor Green
    }
    Write-Host "DiscoveryWorkbench scoreboard JSON: $scoreboardPath" -ForegroundColor Green
    Write-Host "DiscoveryWorkbench scoreboard markdown: $scoreboardMarkdownPath" -ForegroundColor Green
    Write-Host "DiscoveryWorkbench queue JSON: $queuePath" -ForegroundColor Green
    Write-Host "DiscoveryWorkbench queue markdown: $queueMarkdownPath" -ForegroundColor Green
    Write-Host 'DiscoveryWorkbench passed: generated candidate-only scoreboard and next-probe queue.' -ForegroundColor Green
}

function Get-UsageAccessGuardInteger {
    param([object] $Object, [string] $PropertyName, [string] $Context)
    $property = $Object.PSObject.Properties[$PropertyName]
    Assert-UsageAccessGuardCondition ($null -ne $property -and $null -ne $property.Value) "$Context is missing $PropertyName."

    try {
        return [Convert]::ToInt32($property.Value, [Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        throw "UsageAccessCorrelationGuard failed: $PropertyName on $Context is not an integer: $($property.Value)"
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
        { $_ -in @('AssetSignatures', 'AssetSemanticIndex') } {
            $entryCount = 0
            $entriesProperty = $report.PSObject.Properties['Entries']
            if ($null -ne $entriesProperty -and $null -ne $entriesProperty.Value) {
                $entryCount = @($entriesProperty.Value).Count
            }

            Write-Host "schema=$($report.SchemaVersion) inspected=$($report.InspectedPayloads) failed=$($report.Failed) entries=$entryCount"
            $filtersProperty = $report.PSObject.Properties['SemanticCategoryFilters']
            if ($null -ne $filtersProperty -and $null -ne $filtersProperty.Value -and @($filtersProperty.Value).Count -gt 0) {
                Write-Host ('Semantic filters: ' + (@($filtersProperty.Value) -join ', '))
            }
            Write-Host ('Types: ' + (Get-TopText $report.TypeCounts { param($g) "$($g.Value)=$($g.Count)" } 10))
            Write-Host ('Semantic categories: ' + (Get-TopText $report.SemanticCategoryCounts { param($g) "$($g.Value)=$($g.Count)" } 10))
            Write-Host ('Top signatures: ' + (Get-TopText $report.SignatureGroups { param($g) "$($g.Type) $($g.First16) count=$($g.Count) size=$($g.MinSize)..$($g.MaxSize) magic=$($g.MagicLabel)" } 8))
            $xmlGroups = @($report.SignatureGroups | Where-Object {
                $tagProperty = $_.PSObject.Properties['XmlTagCounts']
                $null -ne $tagProperty -and $null -ne $tagProperty.Value -and @($tagProperty.Value).Count -gt 0
            })
            if ($xmlGroups.Count -gt 0) {
                Write-Host ('XML tag families: ' + (Get-TopText $xmlGroups { param($g) "$($g.Type):" + (Get-TopText $g.XmlTagCounts { param($c) "$($c.Value)=$($c.Count)" } 5) } 5))
                Write-Host ('XML attribute families: ' + (Get-TopText $xmlGroups { param($g) "$($g.Type):" + (Get-TopText $g.XmlAttributeCounts { param($c) "$($c.Value)=$($c.Count)" } 5) } 5))
            }
            $xmlStatusGroups = @($report.SignatureGroups | Where-Object {
                $statusProperty = $_.PSObject.Properties['XmlParseStatusCounts']
                $null -ne $statusProperty -and $null -ne $statusProperty.Value -and @($statusProperty.Value).Count -gt 0
            })
            if ($xmlStatusGroups.Count -gt 0) {
                Write-Host ('XML parse statuses: ' + (Get-TopText $xmlStatusGroups { param($g) "$($g.Type):" + (Get-TopText @($g.XmlParseStatusCounts) { param($c) "$($c.Value)=$($c.Count)" } 5) } 5))
            }
            $xmlWarningGroups = @($report.SignatureGroups | Where-Object {
                $warningProperty = $_.PSObject.Properties['XmlParseWarningCounts']
                $null -ne $warningProperty -and $null -ne $warningProperty.Value -and @($warningProperty.Value).Count -gt 0
            })
            if ($xmlWarningGroups.Count -gt 0) {
                Write-Host ('XML parse warnings: ' + (Get-TopText $xmlWarningGroups { param($g) "$($g.Type):" + (Get-TopText @($g.XmlParseWarningCounts) { param($c) "$($c.Value)=$($c.Count)" } 5) } 5))
            }
        }
        'MeshBindings' {
            Write-Host "NIF payloads=$($report.NifPayloads) meshBlocks=$($report.MeshBlocks) links=$($report.CandidateLinks) pairMeshes=$($report.PairCompatibleMeshes) pairLinks=$($report.PairCompatibleLinks)"
            Write-Host ('Top roles: ' + (Get-TopText $report.RoleGroups { param($g) "$($g.Role)=$($g.Count)" }))
            $usageAccessRolesProperty = $report.PSObject.Properties['TopUsageAccessRoles']
            if ($null -ne $usageAccessRolesProperty -and $null -ne $usageAccessRolesProperty.Value) {
                Write-Host ('Top usage/access roles: ' + (Get-TopText @($usageAccessRolesProperty.Value) { param($g) "$(Format-NifUsageAccess $g) $($g.Role)=$($g.Count)" } 8))
            }
            $positionSiblingsProperty = $report.PSObject.Properties['TopPositionSourceSiblings']
            if ($null -ne $positionSiblingsProperty -and $null -ne $positionSiblingsProperty.Value) {
                Write-Host ('Top position source sibling groups: ' + (Get-TopText @($positionSiblingsProperty.Value) { param($g) "$($g.IdPrefix) block#$($g.TargetBlockIndex) payload=$(Get-JsonValueOrDash $g 'DeclaredPayloadBytes') $(Format-NifUsageAccess $g) count=$($g.Count) meshes=$(@($g.MeshBlockIndices | Select-Object -First 4) -join ',') offsets=$(@($g.MeshPayloadOffsets | Select-Object -First 4) -join ',')" } 5))
            }
            $residualTargetProperty = $report.PSObject.Properties['ResidualTargetMeshSizes']
            if ($null -ne $residualTargetProperty -and $null -ne $residualTargetProperty.Value) {
                Write-Host ('Residual target mesh sizes: ' + (Get-TopText @($residualTargetProperty.Value) { param($g) "meshSize=$($g.MeshSize) meshes=$($g.MeshBlockCount) residuals=$($g.ResidualStreamCount) patterns=$($g.ResidualPatternCount)" } 10))
            }
            $residualStreamsProperty = $report.PSObject.Properties['TopResidualStreams']
            if ($null -ne $residualStreamsProperty -and $null -ne $residualStreamsProperty.Value) {
                Write-Host ('Top residual streams (target mesh sizes, known geometry/sentinel roles removed): ' + (Get-TopText @($residualStreamsProperty.Value) { param($g) "meshSize=$($g.MeshSize) count=$($g.Count) stream@$($g.MeshPayloadOffset) payload=$(Get-JsonValueOrDash $g 'DeclaredPayloadBytes') $(Format-NifUsageAccess $g) $($g.Role) c=$($g.RoleConfidence) string=$(Get-JsonValueOrDash $g 'StringValue') ror3=v$(Get-JsonValueOrDash $g 'RotatedFloat3VectorCount') finite=$(Get-JsonValueOrDash $g 'RotatedFloat3FiniteVectorRatio') plausible=$(Get-JsonValueOrDash $g 'RotatedFloat3PlausibleValueRatio') extent=$(Get-JsonValueOrDash $g 'RotatedFloat3MaxExtent') first16=$($g.BodyFirst16)" } 8))
            }
            $positionRoleGroups = @($report.RoleGroups | Where-Object { [string](Get-JsonValueOrDash $_ 'Role') -eq 'position-float3-ror1-lead' })
            if ($positionRoleGroups.Count -gt 0) {
                $positionRole = $positionRoleGroups[0]
                Write-Host ('Position stream lead mesh sizes: ' + (Get-TopText $positionRole.MeshSizes { param($g) "meshSize=$($g.Size):$($g.Count)" } 10))
                Write-Host ('Position stream lead payload sizes: ' + (Get-TopText $positionRole.DeclaredPayloadSizes { param($g) "payload=$($g.Size):$($g.Count)" } 10))
                Write-Host ('Position stream lead samples: ' + (Get-TopText $positionRole.Samples { param($s) "$($s.IdPrefix) meshSize=$($s.MeshSize) mesh=#$($s.MeshBlockIndex) stream@$($s.Stream.MeshPayloadOffset)/#$($s.Stream.TargetBlockIndex) payload=$($s.Stream.DeclaredPayloadBytes) $(Format-NifUsageAccess $s.Stream)" } 5))
            }
            Write-Host ('Top pairings: ' + (Get-TopText $report.TopPairings { param($g) "meshSize=$($g.MeshSize) count=$($g.Count) index[$(Format-NifUsageAccess $g 'IndexDataStreamUsage' 'IndexDataStreamAccess')] $($g.IndexRole)->vertex[$(Format-NifUsageAccess $g 'VertexDataStreamUsage' 'VertexDataStreamAccess')] $($g.VertexRole) v=$($g.VertexCount) max=$($g.MaxIndexObserved) pairs=$(Get-JsonValueOrDash $g 'IndexPairCount') list=$(Get-JsonValueOrDash $g 'TriangleListTriangleCount') strip=$(Get-JsonValueOrDash $g 'TriangleStripWindowCount') cov=$(Get-JsonValueOrDash $g 'MaxIndexCoverageRatio')" }))
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

function Invoke-UsageAccessCorrelationGuard {
    param([Parameter(Mandatory)] [string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "UsageAccessCorrelationGuard failed: report not found: $Path"
    }

    $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $usageAccessRolesProperty = $report.PSObject.Properties['TopUsageAccessRoles']
    Assert-UsageAccessGuardCondition ($null -ne $usageAccessRolesProperty -and $null -ne $usageAccessRolesProperty.Value) 'TopUsageAccessRoles is missing from mesh-binding inventory.'
    $roleGroups = @($usageAccessRolesProperty.Value)

    $expectedRoles = @(
        [pscustomobject]@{ Role = 'uv-float2-ror1-lead'; Usage = '1'; Access = '19'; MinCount = 3000; Family = 'vertex UV rotated-float lead' },
        [pscustomobject]@{ Role = 'normal-float3-ror1-lead'; Usage = '1'; Access = '19'; MinCount = 3000; Family = 'vertex normal rotated-float lead' },
        [pscustomobject]@{ Role = 'index-u16be-strip-lead'; Usage = '0'; Access = '19'; MinCount = 1500; Family = 'index strip lead' },
        [pscustomobject]@{ Role = 'position-float3-ror1-lead'; Usage = '1'; Access = '19'; MinCount = 100; Family = 'position rotated-float lead' },
        [pscustomobject]@{ Role = 'index-u16be-list-lead'; Usage = '0'; Access = '19'; MinCount = 50; Family = 'index list lead' }
    )

    $results = @()
    foreach ($expected in $expectedRoles) {
        $context = "$($expected.Role) usage=$($expected.Usage) access=$($expected.Access)"
        $matches = @($roleGroups | Where-Object {
            [string](Get-JsonValueOrDash $_ 'Role') -eq $expected.Role -and
            [string](Get-JsonValueOrDash $_ 'DataStreamUsage') -eq $expected.Usage -and
            [string](Get-JsonValueOrDash $_ 'DataStreamAccess') -eq $expected.Access
        })

        Assert-UsageAccessGuardCondition ($matches.Count -eq 1) "$context expected exactly one usage/access aggregate, found $($matches.Count)."
        $group = $matches[0]
        $count = Get-UsageAccessGuardInteger $group 'Count' $context
        $highConfidence = Get-UsageAccessGuardInteger $group 'HighConfidenceCount' $context
        Assert-UsageAccessGuardCondition ($count -ge $expected.MinCount) "$context count $count is below expected minimum $($expected.MinCount)."
        Assert-UsageAccessGuardCondition ($highConfidence -ge $expected.MinCount) "$context high-confidence count $highConfidence is below expected minimum $($expected.MinCount)."

        $results += [pscustomobject]@{
            Family = $expected.Family
            Role = $expected.Role
            Usage = $expected.Usage
            Access = $expected.Access
            Count = $count
            HighConfidence = $highConfidence
            MinExpected = $expected.MinCount
        }
    }

    $topPairingsProperty = $report.PSObject.Properties['TopPairings']
    Assert-UsageAccessGuardCondition ($null -ne $topPairingsProperty -and $null -ne $topPairingsProperty.Value) 'TopPairings is missing from mesh-binding inventory.'
    $topPairings = @($topPairingsProperty.Value)
    Assert-UsageAccessGuardCondition ($topPairings.Count -ge 5) "expected at least 5 top pairings, found $($topPairings.Count)."

    $indexVertexPairings = @($topPairings | Where-Object {
        [string](Get-JsonValueOrDash $_ 'IndexRole') -like 'index-*' -and
        [string](Get-JsonValueOrDash $_ 'VertexRole') -match '^(position|normal|uv)-'
    })
    Assert-UsageAccessGuardCondition ($indexVertexPairings.Count -ge 5) "expected at least 5 index-to-vertex top pairings, found $($indexVertexPairings.Count)."

    $pairingExceptions = @($indexVertexPairings | Where-Object {
        [string](Get-JsonValueOrDash $_ 'IndexDataStreamUsage') -ne '0' -or
        [string](Get-JsonValueOrDash $_ 'IndexDataStreamAccess') -ne '19' -or
        [string](Get-JsonValueOrDash $_ 'VertexDataStreamUsage') -ne '1' -or
        [string](Get-JsonValueOrDash $_ 'VertexDataStreamAccess') -ne '19'
    })
    Assert-UsageAccessGuardCondition ($pairingExceptions.Count -eq 0) "found $($pairingExceptions.Count) top pairing usage/access exception(s); expected index usage=0 access=19 -> vertex usage=1 access=19."

    Write-Host "`n--- UsageAccessCorrelationGuard NiDataStream usage/access correlation guard" -ForegroundColor Green
    $results | Sort-Object Count -Descending | Format-Table -AutoSize | Out-Host
    Write-Host "UsageAccessCorrelationGuard pairing check: $($indexVertexPairings.Count) top index-to-vertex pairings, exceptions=0." -ForegroundColor Green
    Write-Host 'UsageAccessCorrelationGuard passed: usage/access correlation remains ranking evidence only; no geometry/export truth was promoted.' -ForegroundColor Green
}

function Invoke-ResidualLeadGuard {
    param([Parameter(Mandatory)] [string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "ResidualLeadGuard failed: report not found: $Path"
    }

    $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $targetProperty = $report.PSObject.Properties['ResidualTargetMeshSizes']
    if ($null -eq $targetProperty -or $null -eq $targetProperty.Value) {
        throw 'ResidualLeadGuard failed: ResidualTargetMeshSizes is missing from mesh-binding inventory.'
    }

    $streamProperty = $report.PSObject.Properties['TopResidualStreams']
    if ($null -eq $streamProperty -or $null -eq $streamProperty.Value) {
        throw 'ResidualLeadGuard failed: TopResidualStreams is missing from mesh-binding inventory.'
    }

    $targets = @($targetProperty.Value)
    $streams = @($streamProperty.Value)
    $requiredMeshSizes = @(297, 305, 321, 325, 329)
    foreach ($meshSize in $requiredMeshSizes) {
        $matches = @($targets | Where-Object { [int](Get-JsonValueOrDash $_ 'MeshSize') -eq $meshSize })
        if ($matches.Count -ne 1) {
            throw "ResidualLeadGuard failed: expected one ResidualTargetMeshSizes entry for meshSize=$meshSize, found $($matches.Count)."
        }
    }

    $mesh305 = @($targets | Where-Object { [int](Get-JsonValueOrDash $_ 'MeshSize') -eq 305 })[0]
    $mesh325 = @($targets | Where-Object { [int](Get-JsonValueOrDash $_ 'MeshSize') -eq 325 })[0]
    if ([int](Get-JsonValueOrDash $mesh305 'ResidualStreamCount') -lt 50) {
        throw 'ResidualLeadGuard failed: meshSize=305 residual stream count dropped below 50.'
    }

    if ([int](Get-JsonValueOrDash $mesh305 'ResidualPatternCount') -lt 20) {
        throw 'ResidualLeadGuard failed: meshSize=305 residual pattern count dropped below 20.'
    }

    if ([int](Get-JsonValueOrDash $mesh325 'ResidualStreamCount') -ne 0) {
        throw 'ResidualLeadGuard failed: meshSize=325 is no longer residual-empty after known-role filtering.'
    }

    $positionLike = @($streams | Where-Object {
        [int](Get-JsonValueOrDash $_ 'MeshSize') -eq 305 -and
        [int](Get-JsonValueOrDash $_ 'MeshPayloadOffset') -eq 188 -and
        [string](Get-JsonValueOrDash $_ 'StringValue') -eq 'POSITION' -and
        [string](Get-JsonValueOrDash $_ 'DataStreamUsage') -eq '1' -and
        [string](Get-JsonValueOrDash $_ 'DataStreamAccess') -eq '19' -and
        [double](Get-JsonValueOrDash $_ 'RotatedFloat3PlausibleValueRatio') -ge 0.80
    })
    if ($positionLike.Count -lt 3) {
        throw "ResidualLeadGuard failed: expected at least three meshSize=305 stream@188 POSITION residual leads with ROR1 plausible ratio >= 0.80, found $($positionLike.Count)."
    }

    $mesh321NoiseRows = @($streams | Where-Object {
        [int](Get-JsonValueOrDash $_ 'MeshSize') -eq 321 -and
        [int](Get-JsonValueOrDash $_ 'MeshPayloadOffset') -eq 204 -and
        [int](Get-JsonValueOrDash $_ 'DeclaredPayloadBytes') -eq 40 -and
        [string](Get-JsonValueOrDash $_ 'StringValue') -eq 'POSITION' -and
        [string](Get-JsonValueOrDash $_ 'DataStreamUsage') -eq '1' -and
        [string](Get-JsonValueOrDash $_ 'DataStreamAccess') -eq '19'
    })
    if ($mesh321NoiseRows.Count -ne 1) {
        throw "ResidualLeadGuard failed: expected exactly one meshSize=321 stream@204 POSITION residual noise-review row, found $($mesh321NoiseRows.Count)."
    }

    $mesh321Noise = $mesh321NoiseRows[0]
    $mesh321Plausible = Get-JsonDoubleOrNull $mesh321Noise 'RotatedFloat3PlausibleValueRatio'
    $mesh321NonZero = Get-JsonDoubleOrNull $mesh321Noise 'RotatedFloat3NonZeroVectorRatio'
    $mesh321Extent = Get-JsonDoubleOrNull $mesh321Noise 'RotatedFloat3MaxExtent'
    if ([int](Get-JsonValueOrDash $mesh321Noise 'Count') -ne 1 -or
        [string](Get-JsonValueOrDash $mesh321Noise 'Role') -ne 'strided-body' -or
        $null -eq $mesh321Plausible -or $mesh321Plausible -gt 0.30 -or
        $null -eq $mesh321NonZero -or $mesh321NonZero -gt 0.34 -or
        $null -eq $mesh321Extent -or [Math]::Abs($mesh321Extent) -gt 0.000001 -or
        -not ([string](Get-JsonValueOrDash $mesh321Noise 'BodyFirst16')).StartsWith('ffff80ff', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'ResidualLeadGuard failed: meshSize=321 stream@204 no longer matches the low-signal sentinel/noise profile; review before treating it as side-stream noise.'
    }

    $mesh329PositionRows = @($streams | Where-Object {
        [int](Get-JsonValueOrDash $_ 'MeshSize') -eq 329 -and
        [int](Get-JsonValueOrDash $_ 'MeshPayloadOffset') -eq 212 -and
        [string](Get-JsonValueOrDash $_ 'StringValue') -eq 'POSITION' -and
        [string](Get-JsonValueOrDash $_ 'DataStreamUsage') -eq '1' -and
        [string](Get-JsonValueOrDash $_ 'DataStreamAccess') -eq '19'
    })
    if ($mesh329PositionRows.Count -ne 1) {
        throw "ResidualLeadGuard failed: expected exactly one meshSize=329 POSITION residual review row, found $($mesh329PositionRows.Count)."
    }

    $mesh329Position = $mesh329PositionRows[0]
    $mesh329Finite = Get-JsonDoubleOrNull $mesh329Position 'RotatedFloat3FiniteVectorRatio'
    $mesh329Plausible = Get-JsonDoubleOrNull $mesh329Position 'RotatedFloat3PlausibleValueRatio'
    $mesh329NonZero = Get-JsonDoubleOrNull $mesh329Position 'RotatedFloat3NonZeroVectorRatio'
    $mesh329Extent = Get-JsonDoubleOrNull $mesh329Position 'RotatedFloat3MaxExtent'
    if ([int](Get-JsonValueOrDash $mesh329Position 'Count') -lt 3 -or
        [string](Get-JsonValueOrDash $mesh329Position 'Role') -ne 'strided-body' -or
        $null -eq $mesh329Finite -or [Math]::Abs($mesh329Finite) -gt 0.000001 -or
        $null -eq $mesh329Plausible -or [Math]::Abs($mesh329Plausible) -gt 0.000001 -or
        $null -eq $mesh329NonZero -or [Math]::Abs($mesh329NonZero) -gt 0.000001 -or
        $null -eq $mesh329Extent -or [Math]::Abs($mesh329Extent) -gt 0.000001) {
        throw 'ResidualLeadGuard failed: meshSize=329 POSITION residual no longer matches the finite=0/plausible=0 side-stream profile; review before treating it as noise.'
    }

    $mesh329ColorPatternRows = @($streams | Where-Object {
        [int](Get-JsonValueOrDash $_ 'MeshSize') -eq 329 -and
        [string](Get-JsonValueOrDash $_ 'StringValue') -eq 'COLOR' -and
        [string](Get-JsonValueOrDash $_ 'Role') -eq 'u32-repeated-pattern-body'
    })
    if ($mesh329ColorPatternRows.Count -lt 10) {
        throw "ResidualLeadGuard failed: expected at least ten meshSize=329 COLOR repeated-pattern side-stream rows, found $($mesh329ColorPatternRows.Count)."
    }

    $mesh329ColorPlausibleMax = 0.0
    foreach ($row in $mesh329ColorPatternRows) {
        $plausible = Get-JsonDoubleOrNull $row 'RotatedFloat3PlausibleValueRatio'
        if ($null -eq $plausible) {
            throw 'ResidualLeadGuard failed: meshSize=329 COLOR repeated-pattern row is missing RotatedFloat3PlausibleValueRatio.'
        }

        $mesh329ColorPlausibleMax = [Math]::Max($mesh329ColorPlausibleMax, $plausible)
    }
    if ($mesh329ColorPlausibleMax -gt 0.000001) {
        throw "ResidualLeadGuard failed: meshSize=329 COLOR repeated-pattern rows now have plausible ratio max=$mesh329ColorPlausibleMax; review as a possible changed signal."
    }
    $mesh329ColorPayloads = @($mesh329ColorPatternRows | ForEach-Object { [int](Get-JsonValueOrDash $_ 'DeclaredPayloadBytes') } | Sort-Object -Unique)

    $mesh297PositionLikeSingletons = @($streams | Where-Object {
        [int](Get-JsonValueOrDash $_ 'MeshSize') -eq 297 -and
        $null -ne (Get-JsonDoubleOrNull $_ 'RotatedFloat3FiniteVectorRatio') -and
        (Get-JsonDoubleOrNull $_ 'RotatedFloat3FiniteVectorRatio') -ge 0.95 -and
        $null -ne (Get-JsonDoubleOrNull $_ 'RotatedFloat3PlausibleValueRatio') -and
        (Get-JsonDoubleOrNull $_ 'RotatedFloat3PlausibleValueRatio') -ge 0.80 -and
        $null -ne (Get-JsonDoubleOrNull $_ 'RotatedFloat3MaxExtent') -and
        (Get-JsonDoubleOrNull $_ 'RotatedFloat3MaxExtent') -gt 0.0001
    })
    $mesh297PromotableWithoutReview = @($mesh297PositionLikeSingletons | Where-Object {
        [int](Get-JsonValueOrDash $_ 'Count') -gt 1 -or
        [string](Get-JsonValueOrDash $_ 'StringValue') -eq 'POSITION'
    })
    if ($mesh297PromotableWithoutReview.Count -ne 0) {
        throw "ResidualLeadGuard failed: meshSize=297 now has $($mesh297PromotableWithoutReview.Count) repeated or POSITION-labeled high-plausible residual row(s); review this as a new lead before treating it as a side stream."
    }

    $residualReviewRows = @(
        [pscustomobject]@{
            MeshSize = 321
            Stream = 'stream@204'
            Payload = Get-JsonValueOrDash $mesh321Noise 'DeclaredPayloadBytes'
            Count = Get-JsonValueOrDash $mesh321Noise 'Count'
            Label = 'POSITION'
            Decision = 'side-stream noise'
            Evidence = "plausible=$mesh321Plausible nonzero=$mesh321NonZero extent=$mesh321Extent first16=$(Get-JsonValueOrDash $mesh321Noise 'BodyFirst16')"
        },
        [pscustomobject]@{
            MeshSize = 329
            Stream = 'stream@212'
            Payload = Get-JsonValueOrDash $mesh329Position 'DeclaredPayloadBytes'
            Count = Get-JsonValueOrDash $mesh329Position 'Count'
            Label = 'POSITION'
            Decision = 'side-stream noise'
            Evidence = "finite=$mesh329Finite plausible=$mesh329Plausible nonzero=$mesh329NonZero extent=$mesh329Extent"
        },
        [pscustomobject]@{
            MeshSize = 329
            Stream = 'stream@296'
            Payload = ('{0}..{1}' -f $mesh329ColorPayloads[0], $mesh329ColorPayloads[-1])
            Count = $mesh329ColorPatternRows.Count
            Label = 'COLOR'
            Decision = 'repeated-pattern side stream'
            Evidence = "rows=$($mesh329ColorPatternRows.Count) plausibleMax=$mesh329ColorPlausibleMax first16=3a3aff3a..."
        }
    ) + @($mesh297PositionLikeSingletons | Sort-Object {[int](Get-JsonValueOrDash $_ 'DeclaredPayloadBytes')} | ForEach-Object {
        [pscustomobject]@{
            MeshSize = 297
            Stream = "stream@$(Get-JsonValueOrDash $_ 'MeshPayloadOffset')"
            Payload = Get-JsonValueOrDash $_ 'DeclaredPayloadBytes'
            Count = Get-JsonValueOrDash $_ 'Count'
            Label = Get-JsonValueOrDash $_ 'StringValue'
            Decision = 'singleton follow-up only'
            Evidence = "plausible=$(Get-JsonValueOrDash $_ 'RotatedFloat3PlausibleValueRatio') extent=$(Get-JsonValueOrDash $_ 'RotatedFloat3MaxExtent') first16=$(Get-JsonValueOrDash $_ 'BodyFirst16')"
        }
    })
    $candidateReviewRows = @($positionLike | Sort-Object {[int](Get-JsonValueOrDash $_ 'DeclaredPayloadBytes')} | ForEach-Object {
        [pscustomobject]@{
            MeshSize = [int](Get-JsonValueOrDash $_ 'MeshSize')
            Stream = "stream@$(Get-JsonValueOrDash $_ 'MeshPayloadOffset')"
            Payload = Get-JsonValueOrDash $_ 'DeclaredPayloadBytes'
            Count = Get-JsonValueOrDash $_ 'Count'
            Label = Get-JsonValueOrDash $_ 'StringValue'
            Decision = 'candidate-only repeated family'
            Evidence = "plausible=$(Get-JsonValueOrDash $_ 'RotatedFloat3PlausibleValueRatio') extent=$(Get-JsonValueOrDash $_ 'RotatedFloat3MaxExtent') first16=$(Get-JsonValueOrDash $_ 'BodyFirst16')"
        }
    })
    $familyReviewRows = @($candidateReviewRows) + @($residualReviewRows)

    function Format-ResidualLeadMarkdownCell {
        param([object] $Value)
        if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) { return '-' }
        return ([string]$Value).Replace('|', '\|')
    }

    $reviewJsonPath = Join-Path (Split-Path -Parent $Path) 'residual-target-family-review.json'
    $reviewMarkdownPath = Join-Path (Split-Path -Parent $Path) 'residual-target-family-review.md'
    $review = [ordered]@{
        Schema = 'residual-target-family-review/v1'
        CandidateOnly = $true
        SourceReport = $Path
        TargetMeshSizes = @($requiredMeshSizes)
        Summary = [ordered]@{
            RepeatedMesh305CandidateRows = @($candidateReviewRows).Count
            Mesh297SingletonFollowUpRows = @($mesh297PositionLikeSingletons).Count
            Mesh321LowSignalRows = @($mesh321NoiseRows).Count
            Mesh329PositionLowSignalRows = @($mesh329PositionRows).Count
            Mesh329ColorRepeatedPatternRows = @($mesh329ColorPatternRows).Count
            Mesh325ResidualStreamCount = [int](Get-JsonValueOrDash $mesh325 'ResidualStreamCount')
        }
        Rows = @($familyReviewRows | Sort-Object MeshSize, Payload)
        Interpretation = 'Candidate-only residual-family routing. Repeated meshSize=305 rows are ranking evidence; meshSize=321/329 POSITION rows remain low-signal side streams; meshSize=329 COLOR rows are repeated-pattern side streams; meshSize=297 rows are single-sample follow-up only.'
    }
    $review | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reviewJsonPath -Encoding UTF8

    $reviewMarkdown = @(
        '# Residual Target Family Review',
        '',
        'Candidate-only review for residual streams in target mesh sizes `297`, `305`, `321`, `325`, and `329`.',
        '',
        'Generated under ignored `Exports/`; do not stage generated asset/discovery output.',
        '',
        ('Summary: meshSize=305 repeated candidates={0}; meshSize=297 singleton follow-ups={1}; meshSize=321 low-signal rows={2}; meshSize=329 POSITION low-signal rows={3}; meshSize=329 COLOR repeated-pattern rows={4}; meshSize=325 residual streams={5}.' -f @($candidateReviewRows).Count, @($mesh297PositionLikeSingletons).Count, @($mesh321NoiseRows).Count, @($mesh329PositionRows).Count, @($mesh329ColorPatternRows).Count, [int](Get-JsonValueOrDash $mesh325 'ResidualStreamCount')),
        '',
        '| Mesh size | Stream | Payload | Count | Label | Decision | Evidence |',
        '|---:|---|---:|---:|---|---|---|'
    )
    foreach ($row in @($familyReviewRows | Sort-Object MeshSize, Payload)) {
        $reviewMarkdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} |' -f
            (Format-ResidualLeadMarkdownCell $row.MeshSize),
            (Format-ResidualLeadMarkdownCell $row.Stream),
            (Format-ResidualLeadMarkdownCell $row.Payload),
            (Format-ResidualLeadMarkdownCell $row.Count),
            (Format-ResidualLeadMarkdownCell $row.Label),
            (Format-ResidualLeadMarkdownCell $row.Decision),
            (Format-ResidualLeadMarkdownCell $row.Evidence))
    }
    $reviewMarkdown += @(
        '',
        'Interpretation: keep these rows as search/ranking evidence only. Do not promote parser role, topology, or export readiness from this report.'
    )
    Set-Content -LiteralPath $reviewMarkdownPath -Value $reviewMarkdown -Encoding UTF8

    Write-Host "`n--- ResidualLeadGuard candidate-only residual lead guard" -ForegroundColor Green
    $targets | Sort-Object {[int](Get-JsonValueOrDash $_ 'MeshSize')} |
        Select-Object MeshSize, MeshBlockCount, ResidualStreamCount, ResidualPatternCount |
        Format-Table -AutoSize | Out-Host
    $positionLike | Sort-Object {[int](Get-JsonValueOrDash $_ 'DeclaredPayloadBytes')} |
        Select-Object MeshSize, MeshPayloadOffset, DeclaredPayloadBytes, Count, StringValue, Role, RotatedFloat3VectorCount, RotatedFloat3PlausibleValueRatio, RotatedFloat3MaxExtent |
        Format-Table -AutoSize | Out-Host
    Write-Host 'Residual side-stream review:' -ForegroundColor DarkGray
    $residualReviewRows | Sort-Object MeshSize, Payload | Format-Table -AutoSize | Out-Host
    Write-Host "ResidualTargetFamilyReview JSON: $reviewJsonPath" -ForegroundColor Green
    Write-Host "ResidualTargetFamilyReview markdown: $reviewMarkdownPath" -ForegroundColor Green
    Write-Host 'ResidualLeadGuard passed: residual leads remain candidate-only ranking evidence; meshSize=321/329 side streams stayed low-signal and no role or geometry truth was promoted.' -ForegroundColor Green
}

function Invoke-ResidualPositionClassifierReport {
    param([Parameter(Mandatory)] [string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "ResidualPositionClassifierReport failed: report not found: $Path"
    }

    $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $streamProperty = $report.PSObject.Properties['TopResidualStreams']
    if ($null -eq $streamProperty -or $null -eq $streamProperty.Value) {
        throw 'ResidualPositionClassifierReport failed: TopResidualStreams is missing from mesh-binding inventory.'
    }

    $streams = @($streamProperty.Value)
    $targetLeads = @($streams | Where-Object {
        [int](Get-JsonValueOrDash $_ 'MeshSize') -eq 305 -and
        [int](Get-JsonValueOrDash $_ 'MeshPayloadOffset') -eq 188 -and
        [string](Get-JsonValueOrDash $_ 'StringValue') -eq 'POSITION' -and
        [string](Get-JsonValueOrDash $_ 'DataStreamUsage') -eq '1' -and
        [string](Get-JsonValueOrDash $_ 'DataStreamAccess') -eq '19'
    })
    if ($targetLeads.Count -eq 0) {
        throw 'ResidualPositionClassifierReport failed: no meshSize=305 stream@188 POSITION usage=1 access=19 residual leads were found.'
    }

    function Format-ResidualFloat3Prefix {
        param([object[]] $Prefix, [int] $Take = 2)
        $items = @($Prefix | Select-Object -First $Take)
        if ($items.Count -eq 0) { return '-' }

        $parts = foreach ($item in $items) {
            'v{0}=({1},{2},{3})' -f
                (Get-JsonValueOrDash $item 'Index'),
                (Get-JsonValueOrDash $item 'X'),
                (Get-JsonValueOrDash $item 'Y'),
                (Get-JsonValueOrDash $item 'Z')
        }
        return ($parts -join '; ')
    }

    $sampleRows = @()
    $rows = foreach ($lead in $targetLeads) {
        $reviewProperty = $lead.PSObject.Properties['StrictRotatedFloat3PositionClassifierReview']
        $review = if ($null -eq $reviewProperty) { $null } else { $reviewProperty.Value }
        $missReasons = if ($null -eq $review -or $null -eq $review.PSObject.Properties['MissReasons'] -or $null -eq $review.MissReasons) {
            '-'
        }
        else {
            (@($review.MissReasons) -join '; ')
        }
        $strictPass = if ($null -eq $review -or $null -eq $review.PSObject.Properties['PassesStrictClassifier']) {
            $false
        }
        else {
            [bool]$review.PassesStrictClassifier
        }
        $maxPlausibleThresholdForSample = if ($null -eq $review -or $null -eq $review.PSObject.Properties['MaxPlausibleValueRatioThresholdForThisSample'] -or $null -eq $review.MaxPlausibleValueRatioThresholdForThisSample) {
            $null
        }
        else {
            [Convert]::ToDouble($review.MaxPlausibleValueRatioThresholdForThisSample, [Globalization.CultureInfo]::InvariantCulture)
        }
        $samplesProperty = $lead.PSObject.Properties['Samples']
        $samples = if ($null -eq $samplesProperty -or $null -eq $samplesProperty.Value) { @() } else { @($samplesProperty.Value) }
        $sampleIds = (@($samples | Select-Object -First 8 | ForEach-Object { "$($_.IdPrefix):mesh#$($_.MeshBlockIndex)" }) -join ',')
        $sampleMeshes = (@($samples | ForEach-Object { "mesh#$($_.MeshBlockIndex)" } | Sort-Object -Unique) -join ',')
        $archiveCount = @($samples | ForEach-Object { $_.ArchiveName } | Sort-Object -Unique).Count
        $leadSampleRows = foreach ($sample in $samples) {
            $stream = Get-JsonValueOrNull $sample 'Stream'
            $roleStats = Get-JsonValueOrNull $stream 'RoleStats'
            $rotatedFloat3Stats = Get-JsonValueOrNull $roleStats 'RotatedFloat3Stats'
            $prefix = Get-JsonValueOrNull $rotatedFloat3Stats 'Prefix'
            [pscustomobject]@{
                Payload = [int](Get-JsonValueOrDash $lead 'DeclaredPayloadBytes')
                IdPrefix = [string](Get-JsonValueOrDash $sample 'IdPrefix')
                ArchiveName = [string](Get-JsonValueOrDash $sample 'ArchiveName')
                EntryIndex = [int](Get-JsonValueOrDash $sample 'EntryIndex')
                ManifestEntryIndex = Get-JsonValueOrDash $sample 'ManifestEntryIndex'
                MeshBlock = "mesh#$(Get-JsonValueOrDash $sample 'MeshBlockIndex')"
                MeshBlockIndex = [int](Get-JsonValueOrDash $sample 'MeshBlockIndex')
                StreamBlock = "#$(Get-JsonValueOrDash $stream 'TargetBlockIndex')"
                TargetSize = Get-JsonValueOrDash $stream 'TargetSize'
                HeaderBytes = Get-JsonValueOrDash $stream 'HeaderBytes'
                BodyFirst16 = [string](Get-JsonValueOrDash $stream 'BodyFirst16')
                VectorCount = Get-JsonValueOrDash $rotatedFloat3Stats 'VectorCount'
                Finite = Get-JsonDoubleOrNull $rotatedFloat3Stats 'FiniteVectorRatio'
                Plausible = Get-JsonDoubleOrNull $rotatedFloat3Stats 'PlausibleValueRatio'
                NonZero = Get-JsonDoubleOrNull $rotatedFloat3Stats 'NonZeroVectorRatio'
                Extent = Get-JsonDoubleOrNull $rotatedFloat3Stats 'MaxExtent'
                Prefix = Format-ResidualFloat3Prefix -Prefix @($prefix) -Take 2
                StrictPass = $strictPass
                MissReasons = $missReasons
            }
        }
        $sampleRows += @($leadSampleRows)

        [pscustomobject]@{
            MeshSize = [int](Get-JsonValueOrDash $lead 'MeshSize')
            Stream = "stream@$($lead.MeshPayloadOffset)"
            Payload = Get-JsonValueOrDash $lead 'DeclaredPayloadBytes'
            Count = [int](Get-JsonValueOrDash $lead 'Count')
            SampleCount = @($samples).Count
            ArchiveCount = $archiveCount
            SampleMeshes = $sampleMeshes
            SampleIds = $sampleIds
            VectorCount = Get-JsonValueOrDash $lead 'RotatedFloat3VectorCount'
            Finite = Get-JsonDoubleOrNull $lead 'RotatedFloat3FiniteVectorRatio'
            Plausible = Get-JsonDoubleOrNull $lead 'RotatedFloat3PlausibleValueRatio'
            NonZero = Get-JsonDoubleOrNull $lead 'RotatedFloat3NonZeroVectorRatio'
            Extent = Get-JsonDoubleOrNull $lead 'RotatedFloat3MaxExtent'
            StrictPass = $strictPass
            MaxPlausibleThresholdForSample = $maxPlausibleThresholdForSample
            MissReasons = $missReasons
        }
    }

    $guardRows = @($rows | Where-Object {
        $null -ne $_.MaxPlausibleThresholdForSample -and
        $null -ne $_.Plausible -and
        $_.Plausible -ge 0.80
    })
    if ($guardRows.Count -lt 3) {
        throw "ResidualPositionClassifierReport failed: expected at least three target residual leads that can support a candidate-only plausible>=0.80 guard, found $($guardRows.Count)."
    }

    $minPlausible = ($guardRows | Measure-Object -Property Plausible -Minimum).Minimum
    $maxPlausible = ($guardRows | Measure-Object -Property Plausible -Maximum).Maximum
    $strictPassCount = @($rows | Where-Object { $_.StrictPass }).Count
    $idMeshRows = @(foreach ($group in @($sampleRows | Group-Object -Property Payload, IdPrefix)) {
        $items = @($group.Group)
        $meshBlocks = @($items | ForEach-Object { $_.MeshBlock } | Sort-Object -Unique)
        $streamBlocks = @($items | ForEach-Object { $_.StreamBlock } | Sort-Object -Unique)
        $bodyFirst16Values = @($items | ForEach-Object { $_.BodyFirst16 } | Sort-Object -Unique)
        $prefixValues = @($items | ForEach-Object { $_.Prefix } | Sort-Object -Unique)
        $hasMesh7 = $meshBlocks -contains 'mesh#7'
        $hasMesh27 = $meshBlocks -contains 'mesh#27'
        $pairStatus = if ($hasMesh7 -and $hasMesh27) {
            'mesh#7+mesh#27'
        }
        elseif ($meshBlocks.Count -gt 1) {
            'multi-mesh'
        }
        else {
            'single-mesh'
        }
        $streamBlocksMatch = $streamBlocks.Count -eq 1
        $bodyFirst16Matches = $bodyFirst16Values.Count -eq 1
        $prefixesMatch = $prefixValues.Count -eq 1
        $pairComparison = if ($pairStatus -eq 'mesh#7+mesh#27' -and $streamBlocksMatch -and $bodyFirst16Matches -and $prefixesMatch) {
            'paired-mesh-same-stream-body-prefix'
        }
        elseif ($pairStatus -eq 'mesh#7+mesh#27') {
            'paired-mesh-different-stream-evidence'
        }
        else {
            $pairStatus
        }
        [pscustomobject]@{
            Payload = [int]$items[0].Payload
            IdPrefix = [string]$items[0].IdPrefix
            SampleCount = $items.Count
            MeshBlocks = ($meshBlocks -join ',')
            PairStatus = $pairStatus
            PairComparison = $pairComparison
            StreamBlocksMatch = $streamBlocksMatch
            BodyFirst16Matches = $bodyFirst16Matches
            PrefixesMatch = $prefixesMatch
            ArchiveNames = (@($items | ForEach-Object { $_.ArchiveName } | Sort-Object -Unique) -join ',')
            EntryIndices = (@($items | ForEach-Object { $_.EntryIndex } | Sort-Object -Unique) -join ',')
            StreamBlocks = ($streamBlocks -join ',')
            BodyFirst16 = ($bodyFirst16Values -join ',')
            Prefixes = (@($prefixValues | Select-Object -First 3) -join ' || ')
            Plausible = $items[0].Plausible
            Extent = $items[0].Extent
            StrictPass = [bool]$items[0].StrictPass
            MissReasons = [string]$items[0].MissReasons
        }
    })
    $payloadRows = @(foreach ($group in @($sampleRows | Group-Object -Property Payload)) {
        $items = @($group.Group)
        $payload = [int]$items[0].Payload
        $payloadIdMeshRows = @($idMeshRows | Where-Object { [int]$_.Payload -eq $payload })
        [pscustomobject]@{
            Payload = $payload
            SampleCount = $items.Count
            IdCount = @($items | ForEach-Object { $_.IdPrefix } | Sort-Object -Unique).Count
            MeshBlocks = (@($items | ForEach-Object { $_.MeshBlock } | Sort-Object -Unique) -join ',')
            Mesh7And27IdCount = @($payloadIdMeshRows | Where-Object { $_.PairStatus -eq 'mesh#7+mesh#27' }).Count
            SingleMeshIdCount = @($payloadIdMeshRows | Where-Object { $_.PairStatus -eq 'single-mesh' }).Count
            CandidateGuard = @($guardRows | Where-Object { [int]$_.Payload -eq $payload }).Count -gt 0
            StrictPassCount = @($items | Where-Object { $_.StrictPass }).Count
            Plausible = $items[0].Plausible
            Extent = $items[0].Extent
            MissReasons = [string]$items[0].MissReasons
        }
    })
    $samePairedRows = @($idMeshRows | Where-Object { $_.PairComparison -eq 'paired-mesh-same-stream-body-prefix' })
    $differentPairedRows = @($idMeshRows | Where-Object { $_.PairComparison -eq 'paired-mesh-different-stream-evidence' })
    $representativeProbeRows = @(foreach ($group in @($samePairedRows | Group-Object -Property Payload)) {
        $idRow = @($group.Group | Sort-Object IdPrefix | Select-Object -First 1)[0]
        $sample = @($sampleRows | Where-Object {
            [int]$_.Payload -eq [int]$idRow.Payload -and
            [string]$_.IdPrefix -eq [string]$idRow.IdPrefix -and
            [int]$_.MeshBlockIndex -eq 7
        } | Select-Object -First 1)
        if ($sample.Count -eq 0) {
            $sample = @($sampleRows | Where-Object {
                [int]$_.Payload -eq [int]$idRow.Payload -and
                [string]$_.IdPrefix -eq [string]$idRow.IdPrefix
            } | Select-Object -First 1)
        }

        if ($sample.Count -eq 0) { continue }

        $selected = $sample[0]
        $streamBlock = ([string]$selected.StreamBlock).TrimStart('#')
        $outPath = Join-Path $Out ("probe-residual-position-payload{0}-{1}-stream{2}.json" -f $selected.Payload, $selected.IdPrefix, $streamBlock)
        [pscustomobject]@{
            Payload = [int]$selected.Payload
            IdPrefix = [string]$selected.IdPrefix
            MeshBlock = [string]$selected.MeshBlock
            StreamBlock = "#$streamBlock"
            BodyFirst16 = [string]$selected.BodyFirst16
            Prefix = [string]$selected.Prefix
            OutPath = $outPath
            Command = ('dotnet run --project "{0}" -- probe-nif-stream-body --root "{1}" --id {2} --stream-block {3} --out "{4}"' -f $Project, $Root, $selected.IdPrefix, $streamBlock, $outPath)
        }
    })
    if ($strictPassCount -ne 0) {
        throw "ResidualPositionClassifierReport failed: expected this residual lane to remain candidate-only with 0 strict classifier passes, found $strictPassCount."
    }

    if ($samePairedRows.Count -lt 8) {
        throw "ResidualPositionClassifierReport failed: expected at least 8 mesh#7+mesh#27 paired rows with matching stream/body/prefix evidence, found $($samePairedRows.Count)."
    }

    if ($differentPairedRows.Count -ne 0) {
        throw "ResidualPositionClassifierReport failed: found $($differentPairedRows.Count) paired mesh rows with divergent stream/body/prefix evidence."
    }

    Write-Host "`n--- ResidualPositionClassifierReport candidate-only strict classifier dry-run" -ForegroundColor Green
    Write-Host 'Strict role classifier remains: VectorCount>=3, FiniteVectorRatio>=0.95, PlausibleValueRatio>=0.95, MaxExtent>=0.0001, NonZeroVectorRatio>=0.50.' -ForegroundColor DarkGray
    Write-Host 'Candidate report threshold: keep repeated residual leads at PlausibleValueRatio>=0.80 as ranking evidence only; do not promote parser roles.' -ForegroundColor DarkGray
    $rows |
        Sort-Object {[int]$_.Payload}, Count |
        Select-Object MeshSize, Stream, Payload, Count, SampleCount, ArchiveCount, SampleMeshes, VectorCount, Finite, Plausible, NonZero, Extent, StrictPass, MaxPlausibleThresholdForSample, MissReasons |
        Format-Table -AutoSize | Out-Host
    Write-Host 'Strict classifier miss reasons by payload:' -ForegroundColor DarkGray
    foreach ($row in @($rows | Sort-Object {[int]$_.Payload}, Count)) {
        $thresholdText = if ($null -eq $row.MaxPlausibleThresholdForSample) { '-' } else { '{0:0.####}' -f $row.MaxPlausibleThresholdForSample }
        Write-Host ("  payload={0} count={1}: misses=[{2}] maxPlausibleThresholdForSample={3}" -f $row.Payload, $row.Count, $row.MissReasons, $thresholdText)
    }
    Write-Host 'Target sample repetition context:' -ForegroundColor DarkGray
    foreach ($row in @($rows | Sort-Object {[int]$_.Payload}, Count)) {
        Write-Host ("  payload={0} samples={1} archives={2} meshes={3} ids={4}" -f $row.Payload, $row.SampleCount, $row.ArchiveCount, $row.SampleMeshes, $row.SampleIds)
    }

    function Format-ResidualMarkdownCell {
        param([object] $Value)
        if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) { return '-' }
        return ([string]$Value).Replace('|', '\|')
    }

    $classifierJsonPath = Join-Path (Split-Path -Parent $Path) 'residual-position-classifier-report.json'
    $markdownPath = Join-Path (Split-Path -Parent $Path) 'residual-position-classifier-report.md'
    $classifierReport = [ordered]@{
        Schema = 'residual-position-classifier-report/v1'
        CandidateOnly = $true
        Target = 'meshSize=305 stream@188 StringValue=POSITION usage=1 access=19'
        SourceReport = $Path
        StrictClassifierRole = 'position-float3-ror1-lead'
        StrictClassifierThresholds = [ordered]@{
            VectorCount = '>= 3'
            FiniteVectorRatio = '>= 0.95'
            PlausibleValueRatio = '>= 0.95'
            MaxExtent = '>= 0.0001'
            NonZeroVectorRatio = '>= 0.50'
        }
        Summary = [ordered]@{
            TargetRows = $rows.Count
            StrictPassRows = $strictPassCount
            CandidateGuardRows = $guardRows.Count
            MinCandidatePlausible = $minPlausible
            MaxCandidatePlausible = $maxPlausible
        }
        Rows = @($rows | Sort-Object {[int]$_.Payload}, Count)
        CandidateGuardRows = @($guardRows | Sort-Object {[int]$_.Payload}, Count)
        Interpretation = 'Strict classifier miss report only. Repeated bounded-position-like rows remain candidate-only and do not promote parser roles, geometry truth, or export readiness.'
    }
    $classifierReport | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $classifierJsonPath -Encoding UTF8
    $markdown = @(
        '# Residual Position Classifier Report',
        '',
        'Candidate-only dry-run for `meshSize=305 stream@188 StringValue=POSITION usage=1 access=19`.',
        '',
        'Strict `position-float3-ror1-lead` classifier remains unchanged:',
        '',
        '```text',
        'VectorCount >= 3',
        'FiniteVectorRatio >= 0.95',
        'PlausibleValueRatio >= 0.95',
        'MaxExtent >= 0.0001',
        'NonZeroVectorRatio >= 0.50',
        '```',
        '',
        ('Summary: target rows={0}, strict-pass={1}, candidate-guard rows={2}, plausible range={3:0.####}..{4:0.####}.' -f $rows.Count, $strictPassCount, $guardRows.Count, $minPlausible, $maxPlausible),
        '',
        '| Payload | Count | Samples | Archives | Meshes | VectorCount | Finite | Plausible | NonZero | Extent | StrictPass | Max plausible threshold | Miss reasons | Sample IDs |',
        '|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---:|---|---|'
    )
    foreach ($row in @($rows | Sort-Object {[int]$_.Payload}, Count)) {
        $thresholdText = if ($null -eq $row.MaxPlausibleThresholdForSample) { '-' } else { '{0:0.####}' -f $row.MaxPlausibleThresholdForSample }
        $markdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} | {9} | {10} | {11} | {12} | {13} |' -f
            (Format-ResidualMarkdownCell $row.Payload),
            (Format-ResidualMarkdownCell $row.Count),
            (Format-ResidualMarkdownCell $row.SampleCount),
            (Format-ResidualMarkdownCell $row.ArchiveCount),
            (Format-ResidualMarkdownCell $row.SampleMeshes),
            (Format-ResidualMarkdownCell $row.VectorCount),
            (Format-ResidualMarkdownCell $row.Finite),
            (Format-ResidualMarkdownCell $row.Plausible),
            (Format-ResidualMarkdownCell $row.NonZero),
            (Format-ResidualMarkdownCell $row.Extent),
            (Format-ResidualMarkdownCell $row.StrictPass),
            (Format-ResidualMarkdownCell $thresholdText),
            (Format-ResidualMarkdownCell $row.MissReasons),
            (Format-ResidualMarkdownCell $row.SampleIds))
    }
    $markdown += @(
        '',
        'Interpretation: repeated bounded-position-like rows remain below the strict plausible-ratio role threshold. Treat this as candidate-only ranking evidence, not promoted geometry truth.'
    )
    Set-Content -LiteralPath $markdownPath -Value $markdown -Encoding UTF8
    $crossTabJsonPath = Join-Path (Split-Path -Parent $Path) 'residual-position-family-crosstab.json'
    $crossTabMarkdownPath = Join-Path (Split-Path -Parent $Path) 'residual-position-family-crosstab.md'
    $crossTab = [ordered]@{
        Schema = 'residual-position-family-crosstab/v1'
        CandidateOnly = $true
        Target = 'meshSize=305 stream@188 StringValue=POSITION usage=1 access=19'
        SourceReport = $Path
        StrictClassifierRole = 'position-float3-ror1-lead'
        StrictClassifierThresholds = [ordered]@{
            VectorCount = '>= 3'
            FiniteVectorRatio = '>= 0.95'
            PlausibleValueRatio = '>= 0.95'
            MaxExtent = '>= 0.0001'
            NonZeroVectorRatio = '>= 0.50'
        }
        Summary = [ordered]@{
            TargetRows = $rows.Count
            SampleRows = @($sampleRows).Count
            StrictPassRows = $strictPassCount
            CandidateGuardRows = $guardRows.Count
            Mesh7And27IdRows = @($idMeshRows | Where-Object { $_.PairStatus -eq 'mesh#7+mesh#27' }).Count
            Mesh7And27SameStreamBodyPrefixRows = $samePairedRows.Count
            SingleMeshIdRows = @($idMeshRows | Where-Object { $_.PairStatus -eq 'single-mesh' }).Count
            MinCandidatePlausible = $minPlausible
            MaxCandidatePlausible = $maxPlausible
        }
        PayloadSummary = @($payloadRows | Sort-Object Payload)
        IdMeshPairs = @($idMeshRows | Sort-Object Payload, IdPrefix)
        RepresentativeProbeCommands = @($representativeProbeRows | Sort-Object Payload, IdPrefix)
        SampleRows = @($sampleRows | Sort-Object Payload, IdPrefix, MeshBlockIndex)
        Interpretation = 'Candidate-only ranking context for repeated residual POSITION-like rows; this does not promote parser role, geometry truth, or export readiness.'
    }
    $crossTab | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $crossTabJsonPath -Encoding UTF8
    $familyMarkdown = @(
        '# Residual Position Family Cross-tab',
        '',
        'Candidate-only grouping for `meshSize=305 stream@188 StringValue=POSITION usage=1 access=19`.',
        '',
        'This report is generated under ignored `Exports/` and is not commit material.',
        '',
        '## Payload summary',
        '',
        '| Payload | Samples | IDs | Mesh blocks | mesh#7+mesh#27 IDs | Single-mesh IDs | Candidate guard | Plausible | Extent | Miss reasons |',
        '|---:|---:|---:|---|---:|---:|---|---:|---:|---|'
    )
    foreach ($row in @($payloadRows | Sort-Object Payload)) {
        $familyMarkdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} | {9} |' -f
            (Format-ResidualMarkdownCell $row.Payload),
            (Format-ResidualMarkdownCell $row.SampleCount),
            (Format-ResidualMarkdownCell $row.IdCount),
            (Format-ResidualMarkdownCell $row.MeshBlocks),
            (Format-ResidualMarkdownCell $row.Mesh7And27IdCount),
            (Format-ResidualMarkdownCell $row.SingleMeshIdCount),
            (Format-ResidualMarkdownCell $row.CandidateGuard),
            (Format-ResidualMarkdownCell $row.Plausible),
            (Format-ResidualMarkdownCell $row.Extent),
            (Format-ResidualMarkdownCell $row.MissReasons))
    }
    $familyMarkdown += @(
        '',
        '## ID / mesh-block repetition',
        '',
        '| Payload | ID | Samples | Mesh blocks | Pair status | Pair comparison | Stream blocks | Body match | Prefix match | Plausible | Extent | Prefix sample |',
        '|---:|---|---:|---|---|---|---|---|---|---:|---:|---|'
    )
    foreach ($row in @($idMeshRows | Sort-Object Payload, IdPrefix)) {
        $familyMarkdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} | {9} | {10} | {11} |' -f
            (Format-ResidualMarkdownCell $row.Payload),
            (Format-ResidualMarkdownCell $row.IdPrefix),
            (Format-ResidualMarkdownCell $row.SampleCount),
            (Format-ResidualMarkdownCell $row.MeshBlocks),
            (Format-ResidualMarkdownCell $row.PairStatus),
            (Format-ResidualMarkdownCell $row.PairComparison),
            (Format-ResidualMarkdownCell $row.StreamBlocks),
            (Format-ResidualMarkdownCell $row.BodyFirst16Matches),
            (Format-ResidualMarkdownCell $row.PrefixesMatch),
            (Format-ResidualMarkdownCell $row.Plausible),
            (Format-ResidualMarkdownCell $row.Extent),
            (Format-ResidualMarkdownCell $row.Prefixes))
    }
    $familyMarkdown += @(
        '',
        '## Representative stream-body probe commands',
        '',
        'One representative `mesh#7` sample per repeated candidate payload. These commands write ignored JSON under `Exports/`.',
        '',
        '| Payload | ID | Mesh | Stream block | Body first16 | Prefix sample | Command |',
        '|---:|---|---|---|---|---|---|'
    )
    foreach ($row in @($representativeProbeRows | Sort-Object Payload, IdPrefix)) {
        $familyMarkdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | `{6}` |' -f
            (Format-ResidualMarkdownCell $row.Payload),
            (Format-ResidualMarkdownCell $row.IdPrefix),
            (Format-ResidualMarkdownCell $row.MeshBlock),
            (Format-ResidualMarkdownCell $row.StreamBlock),
            (Format-ResidualMarkdownCell $row.BodyFirst16),
            (Format-ResidualMarkdownCell $row.Prefix),
            (Format-ResidualMarkdownCell $row.Command))
    }
    $familyMarkdown += @(
        '',
        'Interpretation: `mesh#7+mesh#27` repetition strengthens this as a family-ranking lead, but all rows remain below strict parser role promotion. Keep candidate-only.'
    )
    Set-Content -LiteralPath $crossTabMarkdownPath -Value $familyMarkdown -Encoding UTF8
    Write-Host "ResidualPositionClassifierReport JSON: $classifierJsonPath" -ForegroundColor Green
    Write-Host "ResidualPositionClassifierReport markdown: $markdownPath" -ForegroundColor Green
    Write-Host "ResidualPositionFamilyCrossTab JSON: $crossTabJsonPath" -ForegroundColor Green
    Write-Host "ResidualPositionFamilyCrossTab markdown: $crossTabMarkdownPath" -ForegroundColor Green
    Write-Host ("ResidualPositionFamilyCrossTab guard: same paired stream/body/prefix rows={0}, divergent paired rows=0, strict passes=0." -f $samePairedRows.Count) -ForegroundColor Green
    Write-Host ("ResidualPositionClassifierReport: target rows={0}, strict-pass={1}, candidate-guard rows={2}, plausible range={3:0.####}..{4:0.####}." -f $rows.Count, $strictPassCount, $guardRows.Count, $minPlausible, $maxPlausible) -ForegroundColor Green
    Write-Host 'ResidualPositionClassifierReport passed: strict classifier misses are explained without changing role promotion or proof guards.' -ForegroundColor Green
}

function Invoke-ResidualPositionClusterProbeReport {
    param([Parameter(Mandatory)] [object[]] $ProbeSpecs)

    function Format-ClusterMarkdownCell {
        param([object] $Value)
        if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) { return '-' }
        return ([string]$Value).Replace('|', '\|').Replace("`r", ' ').Replace("`n", ' ')
    }

    function Get-ClusterMeshRow {
        param(
            [Parameter(Mandatory)] [object] $Spec,
            [Parameter(Mandatory)] [string] $Path
        )

        if (-not (Test-Path -LiteralPath $Path)) {
            throw "ResidualPositionClusterProbeReport failed: mesh probe output missing: $Path"
        }

        $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        $meshRows = @($report.Meshes | Where-Object { [int](Get-JsonValueOrDash $_ 'MeshBlockIndex') -eq [int]$Spec.MeshBlock })
        if ($meshRows.Count -ne 1) {
            throw "ResidualPositionClusterProbeReport failed: expected one mesh#$($Spec.MeshBlock) row in $Path, found $($meshRows.Count)."
        }

        $mesh = $meshRows[0]
        $links = @((Get-JsonValueOrNull $mesh 'Streams'))
        $targetLinks = @($links | Where-Object {
            [int](Get-JsonValueOrDash $_ 'MeshPayloadOffset') -eq [int]$Spec.MeshPayloadOffset -and
            [int](Get-JsonValueOrDash $_ 'TargetBlockIndex') -eq [int]$Spec.StreamBlock
        })
        if ($targetLinks.Count -ne 1) {
            throw "ResidualPositionClusterProbeReport failed: expected one stream@$($Spec.MeshPayloadOffset)->#$($Spec.StreamBlock) row for $($Spec.Id) mesh#$($Spec.MeshBlock), found $($targetLinks.Count)."
        }

        $link = $targetLinks[0]
        $attributeSetCount = @((Get-JsonValueOrNull $mesh 'AttributeSets')).Count
        $pairingCount = @((Get-JsonValueOrNull $mesh 'Pairings')).Count
        [pscustomobject]@{
            Payload = [int]$Spec.Payload
            Id = [string]$Spec.Id
            MeshBlock = [int]$Spec.MeshBlock
            MeshSize = [int](Get-JsonValueOrDash $mesh 'MeshSize')
            MeshPayloadOffset = [int](Get-JsonValueOrDash $link 'MeshPayloadOffset')
            TargetBlock = [int](Get-JsonValueOrDash $link 'TargetBlockIndex')
            StreamPayload = [int](Get-JsonValueOrDash $link 'DeclaredPayloadBytes')
            StringValue = [string](Get-JsonValueOrDash $link 'StringValue')
            Role = [string](Get-JsonValueOrDash (Get-JsonValueOrNull $link 'RoleStats') 'PrimaryRole')
            Confidence = [int](Get-JsonValueOrDash (Get-JsonValueOrNull $link 'RoleStats') 'Confidence')
            AttributeSetCount = $attributeSetCount
            PairingCount = $pairingCount
            ReviewRequired = ($attributeSetCount -gt 0 -or $pairingCount -gt 0)
            Decision = if ($attributeSetCount -gt 0 -or $pairingCount -gt 0) {
                'review-required; focused evidence changed but remains candidate-only'
            }
            else {
                'candidate-only; no complete geometry binding'
            }
            OutputPath = $Path
        }
    }

    function Get-ClusterStreamRow {
        param(
            [Parameter(Mandatory)] [object] $Spec,
            [Parameter(Mandatory)] [string] $Path
        )

        if (-not (Test-Path -LiteralPath $Path)) {
            throw "ResidualPositionClusterProbeReport failed: stream-body output missing: $Path"
        }

        $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        $streamRows = @($report.StreamBodies | Where-Object { [int](Get-JsonValueOrDash $_ 'BlockIndex') -eq [int]$Spec.StreamBlock })
        if ($streamRows.Count -ne 1) {
            throw "ResidualPositionClusterProbeReport failed: expected one stream body #$($Spec.StreamBlock) row in $Path, found $($streamRows.Count)."
        }

        $stream = $streamRows[0]
        $stats = Get-JsonValueOrNull $stream 'Stats'
        [pscustomobject]@{
            Payload = [int]$Spec.Payload
            Id = [string]$Spec.Id
            StreamBlock = [int]$Spec.StreamBlock
            DeclaredPayloadBytes = [int](Get-JsonValueOrDash $stream 'DeclaredPayloadBytes')
            Classification = [string](Get-JsonValueOrDash $stats 'Classification')
            BodyFirst16 = [string](Get-JsonValueOrDash $stats 'First16')
            FiniteFloat32Count = [int](Get-JsonValueOrDash $stats 'FiniteFloat32Count')
            PlausibleFloat32Count = [int](Get-JsonValueOrDash $stats 'PlausibleFloat32Count')
            UInt16Distinct = [int](Get-JsonValueOrDash $stats 'UInt16Distinct')
            OutputPath = $Path
        }
    }

    $streamRows = @()
    $meshRows = @()
    foreach ($spec in @($ProbeSpecs | Sort-Object Payload)) {
        $streamPath = Join-Path $Out ("probe-residual-position-payload{0}-{1}-stream{2}.json" -f $spec.Payload, $spec.Id, $spec.StreamBlock)
        Invoke-Checked -Label "ResidualPositionClusterProbeReport payload $($spec.Payload) stream body" -Args @('run', '--project', $Project, '--', 'probe-nif-stream-body', '--root', $Root, '--id', [string]$spec.Id, '--stream-block', [string]$spec.StreamBlock, '--out', $streamPath)
        $streamRows += Get-ClusterStreamRow -Spec $spec -Path $streamPath

        foreach ($meshBlock in @(7, 27)) {
            $meshPath = Join-Path $Out ("probe-nif-mesh-{0}-mesh{1}.json" -f $spec.Id, $meshBlock)
            Invoke-Checked -Label "ResidualPositionClusterProbeReport payload $($spec.Payload) mesh#$meshBlock" -Args @('run', '--project', $Project, '--', 'probe-nif-mesh', '--root', $Root, '--id', [string]$spec.Id, '--mesh-block', [string]$meshBlock, '--out', $meshPath)
            Show-ReportSummary -ModeName 'MeshProbe' -Path $meshPath
            $meshSpec = [pscustomobject]@{
                Payload = $spec.Payload
                Id = $spec.Id
                MeshBlock = $meshBlock
                MeshPayloadOffset = $spec.MeshPayloadOffset
                StreamBlock = $spec.StreamBlock
            }
            $meshRows += Get-ClusterMeshRow -Spec $meshSpec -Path $meshPath
        }
    }

    $payloadRows = @(foreach ($group in @($meshRows | Group-Object Payload)) {
        $items = @($group.Group)
        $stream = @($streamRows | Where-Object { [int]$_.Payload -eq [int]$items[0].Payload } | Select-Object -First 1)[0]
        [pscustomobject]@{
            Payload = [int]$items[0].Payload
            Id = [string]$items[0].Id
            StreamBlock = [int]$stream.StreamBlock
            StreamClassification = [string]$stream.Classification
            BodyFirst16 = [string]$stream.BodyFirst16
            MeshBlocks = (($items | Sort-Object MeshBlock | ForEach-Object { "mesh#$($_.MeshBlock)" }) -join ',')
            MeshRoles = (($items | Sort-Object MeshBlock | ForEach-Object { "mesh#$($_.MeshBlock)=$($_.Role)" }) -join '; ')
            AttributeSetTotal = [int](($items | Measure-Object -Property AttributeSetCount -Sum).Sum)
            PairingTotal = [int](($items | Measure-Object -Property PairingCount -Sum).Sum)
            ReviewRequired = @($items | Where-Object { $_.ReviewRequired }).Count -gt 0
            Decision = if (@($items | Where-Object { $_.ReviewRequired }).Count -gt 0) {
                'review-required; keep candidate-only until guards agree'
            }
            else {
                'candidate-only; no complete geometry binding'
            }
        }
    })

    $reviewRows = @($payloadRows | Where-Object { $_.ReviewRequired })
    $reportPath = Join-Path $Out 'residual-position-cluster-probe-report.json'
    $markdownPath = Join-Path $Out 'residual-position-cluster-probe-report.md'
    $report = [ordered]@{
        Schema = 'residual-position-cluster-probe-report/v1'
        CandidateOnly = $true
        Target = 'meshSize=305 stream@188 StringValue=POSITION usage=1 access=19'
        StrictClassifierThresholdUnchanged = $true
        ExportPromotion = 'blocked'
        PayloadRows = @($payloadRows | Sort-Object Payload)
        StreamRows = @($streamRows | Sort-Object Payload)
        MeshRows = @($meshRows | Sort-Object Payload, MeshBlock)
        Interpretation = 'Focused residual-cluster probe report only. Do not promote parser roles, geometry truth, or OBJ/export readiness from this report.'
    }
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportPath -Encoding UTF8

    $markdown = @(
        '# Residual Position Cluster Probe Report',
        '',
        'Candidate-only focused probe report for `meshSize=305 stream@188 StringValue=POSITION usage=1 access=19`.',
        '',
        '| Payload | ID | Stream body classifier | Body first16 | Mesh roles | Attribute sets | Pairings | Decision |',
        '|---:|---|---|---|---|---:|---:|---|'
    )
    foreach ($row in @($payloadRows | Sort-Object Payload)) {
        $markdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} |' -f
            (Format-ClusterMarkdownCell $row.Payload),
            (Format-ClusterMarkdownCell $row.Id),
            (Format-ClusterMarkdownCell $row.StreamClassification),
            (Format-ClusterMarkdownCell $row.BodyFirst16),
            (Format-ClusterMarkdownCell $row.MeshRoles),
            (Format-ClusterMarkdownCell $row.AttributeSetTotal),
            (Format-ClusterMarkdownCell $row.PairingTotal),
            (Format-ClusterMarkdownCell $row.Decision))
    }
    $markdown += @(
        '',
        'Interpretation: this report compares repeated residual payload clusters against focused mesh#7/mesh#27 probes. It is search evidence only; strict classifier thresholds and export gates remain unchanged.'
    )
    Set-Content -LiteralPath $markdownPath -Value $markdown -Encoding UTF8

    Write-Host "`n--- ResidualPositionClusterProbeReport candidate-only residual cluster probes" -ForegroundColor Green
    $payloadRows | Sort-Object Payload | Format-Table -AutoSize | Out-Host
    Write-Host "ResidualPositionClusterProbeReport JSON: $reportPath" -ForegroundColor Green
    Write-Host "ResidualPositionClusterProbeReport markdown: $markdownPath" -ForegroundColor Green
    if ($reviewRows.Count -gt 0) {
        Write-Host "ResidualPositionClusterProbeReport review-required rows: $($reviewRows.Count). Candidate-only boundary preserved." -ForegroundColor Yellow
    }
    Write-Host 'ResidualPositionClusterProbeReport passed: strict thresholds unchanged and OBJ/export remains blocked.' -ForegroundColor Green
}

function Invoke-PositionSourceGapReport {
    param([Parameter(Mandatory)] [string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "PositionSourceGapReport failed: report not found: $Path"
    }

    $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $roleGroups = @($report.RoleGroups)
    $topPairings = @((Get-JsonValueOrNull $report 'TopPairings'))
    $attributeSets = @((Get-JsonValueOrNull $report 'TopAttributeSets'))
    $residualTargets = @((Get-JsonValueOrNull $report 'ResidualTargetMeshSizes'))
    $residualStreams = @((Get-JsonValueOrNull $report 'TopResidualStreams'))
    if ($roleGroups.Count -eq 0 -or $topPairings.Count -eq 0 -or $attributeSets.Count -eq 0 -or $residualTargets.Count -eq 0) {
        throw 'PositionSourceGapReport failed: MeshBindings report is missing role, pairing, attribute-set, or residual target data.'
    }

    $positionRole = @($roleGroups | Where-Object { [string](Get-JsonValueOrDash $_ 'Role') -eq 'position-float3-ror1-lead' } | Select-Object -First 1)
    if ($positionRole.Count -ne 1) {
        throw "PositionSourceGapReport failed: expected one position-float3-ror1-lead role group, found $($positionRole.Count)."
    }

    function Get-PositionLeadCountForMeshSize {
        param([int] $MeshSize)
        $match = @($positionRole[0].MeshSizes | Where-Object { [int](Get-JsonValueOrDash $_ 'Size') -eq $MeshSize } | Select-Object -First 1)
        if ($match.Count -eq 0) { return 0 }
        return [int](Get-JsonValueOrDash $match[0] 'Count')
    }

    function Get-PositionGapDecision {
        param(
            [int] $MeshSize,
            [int] $PositionLeadCount,
            [double] $TopologyPairingCount,
            [int] $ResidualStreamCount,
            [int] $ResidualPositionCandidateRows,
            [int] $AttributeSetCount)

        if ($MeshSize -eq 305 -and $ResidualPositionCandidateRows -ge 5) {
            return 'residual-position-candidate-family'
        }

        if ($MeshSize -eq 325 -and $TopologyPairingCount -ge 300 -and $PositionLeadCount -le 5 -and $ResidualStreamCount -eq 0) {
            return 'topology-rich sparse-position singleton lead'
        }

        if ($MeshSize -eq 297 -and $AttributeSetCount -ge 4) {
            return 'topology-proof anchor; residual singleton follow-up only'
        }

        if ($MeshSize -eq 329 -and $AttributeSetCount -ge 20 -and $ResidualStreamCount -ge 40) {
            return 'attribute-rich family; residual side-streams low-signal'
        }

        if ($MeshSize -in @(321, 329) -and $TopologyPairingCount -ge 100) {
            return 'topology-rich family; residual side-streams low-signal'
        }

        return 'context-only'
    }

    $targetMeshSizes = @(297, 305, 321, 325, 329)
    $rows = foreach ($meshSize in $targetMeshSizes) {
        $pairings = @($topPairings | Where-Object {
            [int](Get-JsonValueOrDash $_ 'MeshSize') -eq $meshSize -and
            [string](Get-JsonValueOrDash $_ 'IndexRole') -like 'index-*'
        })
        $attributeRows = @($attributeSets | Where-Object { [int](Get-JsonValueOrDash $_ 'MeshSize') -eq $meshSize })
        $residualTarget = @($residualTargets | Where-Object { [int](Get-JsonValueOrDash $_ 'MeshSize') -eq $meshSize } | Select-Object -First 1)
        $meshResidualRows = @($residualStreams | Where-Object { [int](Get-JsonValueOrDash $_ 'MeshSize') -eq $meshSize })
        $residualPositionCandidateRows = @($meshResidualRows | Where-Object {
            [string](Get-JsonValueOrDash $_ 'StringValue') -eq 'POSITION' -and
            $null -ne (Get-JsonDoubleOrNull $_ 'RotatedFloat3PlausibleValueRatio') -and
            (Get-JsonDoubleOrNull $_ 'RotatedFloat3PlausibleValueRatio') -ge 0.80
        })
        $positionLeadCount = Get-PositionLeadCountForMeshSize -MeshSize $meshSize
        $positionSamples = @($positionRole[0].Samples |
            Where-Object { [int](Get-JsonValueOrDash $_ 'MeshSize') -eq $meshSize } |
            Select-Object -First 4 |
            ForEach-Object { "$($_.IdPrefix):mesh#$($_.MeshBlockIndex):stream@$(Get-JsonValueOrDash $_.Stream 'MeshPayloadOffset')/#$(Get-JsonValueOrDash $_.Stream 'TargetBlockIndex'):payload=$(Get-JsonValueOrDash $_.Stream 'DeclaredPayloadBytes')" })
        $pairingCount = Get-MeasureSumOrZero -Items $pairings -PropertyName 'Count'
        $normalPairingCount = Get-MeasureSumOrZero -Items @($pairings | Where-Object { [string](Get-JsonValueOrDash $_ 'VertexRole') -like 'normal*' }) -PropertyName 'Count'
        $uvPairingCount = Get-MeasureSumOrZero -Items @($pairings | Where-Object { [string](Get-JsonValueOrDash $_ 'VertexRole') -like 'uv*' }) -PropertyName 'Count'
        $positionPairingCount = Get-MeasureSumOrZero -Items @($pairings | Where-Object { [string](Get-JsonValueOrDash $_ 'VertexRole') -like 'position*' }) -PropertyName 'Count'
        $topologyHints = @($attributeRows |
            Sort-Object -Property @{Expression = 'Count'; Descending = $true}, @{Expression = 'VertexCount'; Descending = $true} |
            Select-Object -First 4 |
            ForEach-Object { "v=$(Get-JsonValueOrDash $_ 'VertexCount') count=$(Get-JsonValueOrDash $_ 'Count') $((Get-JsonValueOrNull $_ 'Topology').PrimaryTopology)" })
        $residualHints = @($meshResidualRows |
            Sort-Object -Property @{Expression = 'Count'; Descending = $true}, DeclaredPayloadBytes |
            Select-Object -First 4 |
            ForEach-Object { "stream@$(Get-JsonValueOrDash $_ 'MeshPayloadOffset') payload=$(Get-JsonValueOrDash $_ 'DeclaredPayloadBytes') $(Get-JsonValueOrDash $_ 'StringValue') plausible=$(Get-JsonValueOrDash $_ 'RotatedFloat3PlausibleValueRatio')" })
        $residualStreamCount = if ($residualTarget.Count -gt 0) { [int](Get-JsonValueOrDash $residualTarget[0] 'ResidualStreamCount') } else { 0 }
        $decision = Get-PositionGapDecision `
            -MeshSize $meshSize `
            -PositionLeadCount $positionLeadCount `
            -TopologyPairingCount $pairingCount `
            -ResidualStreamCount $residualStreamCount `
            -ResidualPositionCandidateRows @($residualPositionCandidateRows).Count `
            -AttributeSetCount $attributeRows.Count

        [pscustomobject]@{
            MeshSize = $meshSize
            PositionLeadCount = $positionLeadCount
            TopPairingRows = $pairings.Count
            TopologyPairingCount = $pairingCount
            NormalPairingCount = $normalPairingCount
            UvPairingCount = $uvPairingCount
            PositionPairingCount = $positionPairingCount
            AttributeSetRows = $attributeRows.Count
            ResidualStreamCount = $residualStreamCount
            ResidualPositionCandidateRows = @($residualPositionCandidateRows).Count
            Decision = $decision
            PositionSamples = ($positionSamples -join ' | ')
            TopologyHints = ($topologyHints -join ' | ')
            ResidualHints = ($residualHints -join ' | ')
        }
    }

    $mesh325 = @($rows | Where-Object { $_.MeshSize -eq 325 })[0]
    if ($mesh325.TopologyPairingCount -lt 300 -or $mesh325.ResidualStreamCount -ne 0) {
        throw 'PositionSourceGapReport failed: meshSize=325 no longer matches the topology-rich residual-empty gap profile; review before reranking.'
    }

    $mesh305 = @($rows | Where-Object { $_.MeshSize -eq 305 })[0]
    if ($mesh305.ResidualPositionCandidateRows -lt 5) {
        throw "PositionSourceGapReport failed: meshSize=305 residual-position candidate rows dropped below 5 ($($mesh305.ResidualPositionCandidateRows))."
    }

    $jsonPath = Join-Path (Split-Path -Parent $Path) 'position-source-gap-report.json'
    $markdownPath = Join-Path (Split-Path -Parent $Path) 'position-source-gap-report.md'
    $summary = [ordered]@{
        Schema = 'position-source-gap-report/v1'
        CandidateOnly = $true
        SourceReport = $Path
        TargetMeshSizes = $targetMeshSizes
        Rows = @($rows | Sort-Object MeshSize)
        Interpretation = 'Candidate-only ranking report for position-source search gaps. Does not promote geometry truth, topology truth, or export readiness.'
    }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $markdown = @(
        '# Position Source Gap Report',
        '',
        'Candidate-only ranking report for topology-rich mesh families where position-source evidence is sparse, residual-only, or side-stream/noise.',
        '',
        'Generated under ignored `Exports/`; do not stage generated discovery output.',
        '',
        '| Mesh size | Position leads | Pairing count | Normal pairs | UV pairs | Attribute rows | Residuals | Residual POSITION candidates | Decision |',
        '|---:|---:|---:|---:|---:|---:|---:|---:|---|'
    )
    foreach ($row in @($rows | Sort-Object MeshSize)) {
        $markdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} |' -f
            (Format-WorkflowMarkdownCell $row.MeshSize),
            (Format-WorkflowMarkdownCell $row.PositionLeadCount),
            (Format-WorkflowMarkdownCell $row.TopologyPairingCount),
            (Format-WorkflowMarkdownCell $row.NormalPairingCount),
            (Format-WorkflowMarkdownCell $row.UvPairingCount),
            (Format-WorkflowMarkdownCell $row.AttributeSetRows),
            (Format-WorkflowMarkdownCell $row.ResidualStreamCount),
            (Format-WorkflowMarkdownCell $row.ResidualPositionCandidateRows),
            (Format-WorkflowMarkdownCell $row.Decision))
    }

    $markdown += @(
        '',
        '## Topology and residual hints',
        '',
        '| Mesh size | Position samples | Topology hints | Residual hints |',
        '|---:|---|---|---|'
    )
    foreach ($row in @($rows | Sort-Object MeshSize)) {
        $markdown += ('| {0} | {1} | {2} | {3} |' -f
            (Format-WorkflowMarkdownCell $row.MeshSize),
            (Format-WorkflowMarkdownCell $row.PositionSamples),
            (Format-WorkflowMarkdownCell $row.TopologyHints),
            (Format-WorkflowMarkdownCell $row.ResidualHints))
    }

    $markdown += @(
        '',
        'Interpretation: use this to prioritize offline parser/probe work only. Do not treat sparse position leads, residual streams, or semantic hints as export-ready geometry truth.'
    )
    Set-Content -LiteralPath $markdownPath -Value $markdown -Encoding UTF8

    Write-Host "`n--- PositionSourceGapReport candidate-only position-source gap ranking" -ForegroundColor Green
    $rows | Sort-Object MeshSize | Select-Object MeshSize, PositionLeadCount, TopologyPairingCount, NormalPairingCount, UvPairingCount, AttributeSetRows, ResidualStreamCount, ResidualPositionCandidateRows, Decision | Format-Table -AutoSize | Out-Host
    Write-Host "PositionSourceGapReport JSON: $jsonPath" -ForegroundColor Green
    Write-Host "PositionSourceGapReport markdown: $markdownPath" -ForegroundColor Green
    Write-Host 'PositionSourceGapReport passed: topology-rich families are ranked without promoting geometry/export truth.' -ForegroundColor Green
}

function New-PositionSourceSiblingProbeRow {
    param([Parameter(Mandatory)] [object] $Spec)

    $path = [string]$Spec.Path
    if (-not (Test-Path -LiteralPath $path)) {
        throw "PositionSourceSiblingProbeReport failed: probe report not found: $path"
    }

    $report = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    $meshBlock = [int]$Spec.MeshBlock
    $meshEntries = @($report.Meshes | Where-Object { [int](Get-JsonValueOrDash $_ 'MeshBlockIndex') -eq $meshBlock })
    if ($meshEntries.Count -ne 1) {
        throw "PositionSourceSiblingProbeReport failed: expected exactly one mesh#$meshBlock entry in $path, found $($meshEntries.Count)."
    }

    $mesh = $meshEntries[0]
    $attributeSets = @($mesh.AttributeSets)
    if ($attributeSets.Count -ne 1) {
        throw "PositionSourceSiblingProbeReport failed: expected exactly one attribute-set row for $($Spec.Id) mesh#$meshBlock, found $($attributeSets.Count)."
    }

    $attr = $attributeSets[0]
    $pairingsValue = Get-JsonValueOrNull $mesh 'Pairings'
    $extraValue = Get-JsonValueOrNull $attr 'ExtraStreams'
    $pairingCount = if ($null -eq $pairingsValue) { 0 } else { @($pairingsValue).Count }
    $extraStreamCount = if ($null -eq $extraValue) { 0 } else { @($extraValue).Count }
    $topology = Get-JsonValueOrNull $attr 'Topology'

    [pscustomobject]@{
        Pair = [string]$Spec.Pair
        PairLabel = [string]$Spec.PairLabel
        Id = [string]$Spec.Id
        MeshBlock = $meshBlock
        MeshSize = [int](Get-JsonValueOrDash $attr 'MeshSize')
        VertexCount = [int](Get-JsonValueOrDash $attr 'VertexCount')
        PrimaryTopology = [string]$topology.PrimaryTopology
        TopologyConfidence = [int](Get-JsonValueOrDash $topology 'Confidence')
        PositionMeshPayloadOffset = [int](Get-JsonValueOrDash $attr 'PositionMeshPayloadOffset')
        PositionBlockIndex = [int](Get-JsonValueOrDash $attr 'PositionBlockIndex')
        PositionDeclaredPayloadBytes = [int](Get-JsonValueOrDash $attr 'PositionDeclaredPayloadBytes')
        PositionDataStreamUsage = [string](Get-JsonValueOrDash $attr 'PositionDataStreamUsage')
        PositionDataStreamAccess = [string](Get-JsonValueOrDash $attr 'PositionDataStreamAccess')
        PositionRole = [string](Get-JsonValueOrDash $attr 'PositionRole')
        NormalMeshPayloadOffset = [int](Get-JsonValueOrDash $attr 'NormalMeshPayloadOffset')
        NormalBlockIndex = [int](Get-JsonValueOrDash $attr 'NormalBlockIndex')
        NormalDeclaredPayloadBytes = [int](Get-JsonValueOrDash $attr 'NormalDeclaredPayloadBytes')
        UvMeshPayloadOffset = [int](Get-JsonValueOrDash $attr 'UvMeshPayloadOffset')
        UvBlockIndex = [int](Get-JsonValueOrDash $attr 'UvBlockIndex')
        UvDeclaredPayloadBytes = [int](Get-JsonValueOrDash $attr 'UvDeclaredPayloadBytes')
        PairingCount = $pairingCount
        ExtraStreamCount = $extraStreamCount
        ProbePath = $path
    }
}

function Get-PositionSourceSiblingUniqueCount {
    param([object[]] $Rows, [string] $PropertyName)
    return @($Rows | ForEach-Object { $_.$PropertyName } | Sort-Object -Unique).Count
}

function Invoke-PositionSourceSiblingProbeReport {
    param([Parameter(Mandatory)] [object[]] $ProbeSpecs)

    $rows = @($ProbeSpecs | ForEach-Object { New-PositionSourceSiblingProbeRow -Spec $_ })
    $pairs = @($rows | Group-Object Pair)
    if ($pairs.Count -lt 2) {
        throw "PositionSourceSiblingProbeReport failed: expected at least two sibling pairs, found $($pairs.Count)."
    }

    $pairSummaries = @()
    foreach ($pair in $pairs) {
        $pairRows = @($pair.Group | Sort-Object MeshBlock)
        if ($pairRows.Count -ne 2) {
            throw "PositionSourceSiblingProbeReport failed: pair '$($pair.Name)' expected exactly two probe rows, found $($pairRows.Count)."
        }

        $positionShared =
            (Get-PositionSourceSiblingUniqueCount -Rows $pairRows -PropertyName 'PositionBlockIndex') -eq 1 -and
            (Get-PositionSourceSiblingUniqueCount -Rows $pairRows -PropertyName 'PositionDeclaredPayloadBytes') -eq 1 -and
            (Get-PositionSourceSiblingUniqueCount -Rows $pairRows -PropertyName 'PositionDataStreamUsage') -eq 1 -and
            (Get-PositionSourceSiblingUniqueCount -Rows $pairRows -PropertyName 'PositionDataStreamAccess') -eq 1 -and
            (Get-PositionSourceSiblingUniqueCount -Rows $pairRows -PropertyName 'PositionRole') -eq 1
        if (-not $positionShared) {
            throw "PositionSourceSiblingProbeReport failed: pair '$($pair.Name)' no longer has shared position stream block/payload/usage/access/role evidence."
        }

        if ((Get-PositionSourceSiblingUniqueCount -Rows $pairRows -PropertyName 'VertexCount') -ne 1) {
            throw "PositionSourceSiblingProbeReport failed: pair '$($pair.Name)' no longer has matching vertex-count evidence."
        }

        if ((Get-PositionSourceSiblingUniqueCount -Rows $pairRows -PropertyName 'PrimaryTopology') -ne 1) {
            throw "PositionSourceSiblingProbeReport failed: pair '$($pair.Name)' no longer has matching primary topology evidence."
        }

        $first = $pairRows[0]
        $second = $pairRows[1]
        $meshSizeDelta = [int]$second.MeshSize - [int]$first.MeshSize
        $positionOffsetDelta = [int]$second.PositionMeshPayloadOffset - [int]$first.PositionMeshPayloadOffset
        $positionOffsetPattern = if ($positionOffsetDelta -eq 0) {
            'same mesh payload offset'
        }
        elseif ($positionOffsetDelta -eq $meshSizeDelta) {
            "mesh payload offset shifts with mesh-size delta ($positionOffsetDelta)"
        }
        else {
            "mesh payload offset delta $positionOffsetDelta; mesh-size delta $meshSizeDelta"
        }

        $pairSummaries += [pscustomobject]@{
            Pair = [string]$pair.Name
            PairLabel = [string]$first.PairLabel
            Id = [string]$first.Id
            MeshBlocks = (@($pairRows | ForEach-Object { "mesh#$($_.MeshBlock)" }) -join ', ')
            MeshSizes = (@($pairRows | ForEach-Object { [string]$_.MeshSize }) -join ', ')
            VertexCount = [int]$first.VertexCount
            PrimaryTopology = [string]$first.PrimaryTopology
            SharedPositionStream = "block#$($first.PositionBlockIndex) payload=$($first.PositionDeclaredPayloadBytes) usage=$($first.PositionDataStreamUsage) access=$($first.PositionDataStreamAccess) role=$($first.PositionRole)"
            PositionOffsetPattern = $positionOffsetPattern
            NormalStreams = (@($pairRows | ForEach-Object { "mesh#$($_.MeshBlock):block#$($_.NormalBlockIndex) payload=$($_.NormalDeclaredPayloadBytes)" }) -join ' | ')
            UvStreams = (@($pairRows | ForEach-Object { "mesh#$($_.MeshBlock):block#$($_.UvBlockIndex) payload=$($_.UvDeclaredPayloadBytes)" }) -join ' | ')
            Decision = 'shared-position-stream sibling evidence; candidate-only source ranking, not geometry/export truth'
        }
    }

    $jsonPath = Join-Path $Out 'position-source-sibling-probe-report.json'
    $markdownPath = Join-Path $Out 'position-source-sibling-probe-report.md'
    $summary = [ordered]@{
        Schema = 'position-source-sibling-probe-report/v1'
        CandidateOnly = $true
        SourceProbes = @($ProbeSpecs | ForEach-Object { [string]$_.Path })
        PairSummaries = @($pairSummaries | Sort-Object Pair)
        ProbeRows = @($rows | Sort-Object Pair, MeshBlock)
        Interpretation = 'Shared position stream blocks across sibling mesh blocks are parser-search evidence only. This report does not promote geometry truth, topology truth, or export readiness.'
    }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $markdown = @(
        '# Position Source Sibling Probe Report',
        '',
        'Candidate-only comparison of focused `probe-nif-mesh` outputs for sibling meshes with sparse or shifted position-source evidence.',
        '',
        'Generated under ignored `Exports/`; do not stage generated discovery output.',
        '',
        '## Pair summary',
        '',
        '| Pair | ID | Meshes | Mesh sizes | Vertex count | Topology | Shared position stream | Offset pattern | Decision |',
        '|---|---|---|---|---:|---|---|---|---|'
    )
    foreach ($pairSummary in @($pairSummaries | Sort-Object Pair)) {
        $markdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} |' -f
            (Format-WorkflowMarkdownCell $pairSummary.PairLabel),
            (Format-WorkflowMarkdownCell $pairSummary.Id),
            (Format-WorkflowMarkdownCell $pairSummary.MeshBlocks),
            (Format-WorkflowMarkdownCell $pairSummary.MeshSizes),
            (Format-WorkflowMarkdownCell $pairSummary.VertexCount),
            (Format-WorkflowMarkdownCell $pairSummary.PrimaryTopology),
            (Format-WorkflowMarkdownCell $pairSummary.SharedPositionStream),
            (Format-WorkflowMarkdownCell $pairSummary.PositionOffsetPattern),
            (Format-WorkflowMarkdownCell $pairSummary.Decision))
    }

    $markdown += @(
        '',
        '## Probe rows',
        '',
        '| Pair | Mesh | Mesh size | Position | Normal | UV | Pairings | Extra streams |',
        '|---|---:|---:|---|---|---|---:|---:|'
    )
    foreach ($row in @($rows | Sort-Object Pair, MeshBlock)) {
        $positionText = "stream@$($row.PositionMeshPayloadOffset)/#$($row.PositionBlockIndex) payload=$($row.PositionDeclaredPayloadBytes) usage=$($row.PositionDataStreamUsage) access=$($row.PositionDataStreamAccess)"
        $normalText = "stream@$($row.NormalMeshPayloadOffset)/#$($row.NormalBlockIndex) payload=$($row.NormalDeclaredPayloadBytes)"
        $uvText = "stream@$($row.UvMeshPayloadOffset)/#$($row.UvBlockIndex) payload=$($row.UvDeclaredPayloadBytes)"
        $markdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} |' -f
            (Format-WorkflowMarkdownCell $row.PairLabel),
            (Format-WorkflowMarkdownCell $row.MeshBlock),
            (Format-WorkflowMarkdownCell $row.MeshSize),
            (Format-WorkflowMarkdownCell $positionText),
            (Format-WorkflowMarkdownCell $normalText),
            (Format-WorkflowMarkdownCell $uvText),
            (Format-WorkflowMarkdownCell $row.PairingCount),
            (Format-WorkflowMarkdownCell $row.ExtraStreamCount))
    }

    $markdown += @(
        '',
        'Interpretation: shared position stream blocks across sibling meshes are a narrow parser-search clue. Normal/UV streams remain separate sibling-local blocks, and no OBJ/export gate is changed.'
    )
    Set-Content -LiteralPath $markdownPath -Value $markdown -Encoding UTF8

    Write-Host "`n--- PositionSourceSiblingProbeReport candidate-only sibling position-source comparison" -ForegroundColor Green
    $pairSummaries | Sort-Object Pair | Select-Object PairLabel, Id, MeshBlocks, MeshSizes, VertexCount, PrimaryTopology, SharedPositionStream, PositionOffsetPattern | Format-Table -AutoSize | Out-Host
    Write-Host "PositionSourceSiblingProbeReport JSON: $jsonPath" -ForegroundColor Green
    Write-Host "PositionSourceSiblingProbeReport markdown: $markdownPath" -ForegroundColor Green
    Write-Host 'PositionSourceSiblingProbeReport passed: sibling position-source evidence stayed candidate-only and no geometry/export truth was promoted.' -ForegroundColor Green
}

function New-PositionSourceRepresentativeProbeRow {
    param([Parameter(Mandatory)] [object] $Spec)

    $path = [string]$Spec.Path
    if (-not (Test-Path -LiteralPath $path)) {
        throw "PositionSourceSiblingRepresentativeProbeReport failed: probe report not found: $path"
    }

    $report = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    $meshBlock = [int]$Spec.MeshBlock
    $meshEntries = @($report.Meshes | Where-Object { [int](Get-JsonValueOrDash $_ 'MeshBlockIndex') -eq $meshBlock })
    if ($meshEntries.Count -ne 1) {
        throw "PositionSourceSiblingRepresentativeProbeReport failed: expected exactly one mesh#$meshBlock entry in $path, found $($meshEntries.Count)."
    }

    $mesh = $meshEntries[0]
    $attributeSets = @($mesh.AttributeSets)
    $positionStreams = @($mesh.Streams | Where-Object { [string]$_.RoleStats.PrimaryRole -like 'position-float3*' })
    $normalStreams = @($mesh.Streams | Where-Object { [string]$_.RoleStats.PrimaryRole -like 'normal*' })
    $uvStreams = @($mesh.Streams | Where-Object { [string]$_.RoleStats.PrimaryRole -like 'uv*' })
    $sideStreams = @($mesh.Streams | Where-Object {
        [string]$_.RoleStats.PrimaryRole -notlike 'position-float3*' -and
        [string]$_.RoleStats.PrimaryRole -notlike 'normal*' -and
        [string]$_.RoleStats.PrimaryRole -notlike 'uv*'
    })
    $attributeSummary = 'none'
    if ($attributeSets.Count -gt 0) {
        $attr = $attributeSets[0]
        $attributeSummary = "v=$($attr.VertexCount) p@$($attr.PositionMeshPayloadOffset)/#$($attr.PositionBlockIndex) n@$($attr.NormalMeshPayloadOffset)/#$($attr.NormalBlockIndex) uv@$($attr.UvMeshPayloadOffset)/#$($attr.UvBlockIndex) topology=$($attr.Topology.PrimaryTopology) extras=$(@($attr.ExtraStreams).Count)"
    }

    [pscustomobject]@{
        Pair = [string]$Spec.Pair
        PairLabel = [string]$Spec.PairLabel
        Id = [string]$Spec.Id
        MeshBlock = $meshBlock
        MeshSize = [int](Get-JsonValueOrDash $mesh 'MeshSize')
        PositionStreams = @($positionStreams | ForEach-Object { [pscustomobject]@{ MeshPayloadOffset = [int]$_.MeshPayloadOffset; TargetBlockIndex = [int]$_.TargetBlockIndex; Payload = [int]$_.DeclaredPayloadBytes; Role = [string]$_.RoleStats.PrimaryRole } })
        NormalStreams = @($normalStreams | ForEach-Object { [pscustomobject]@{ MeshPayloadOffset = [int]$_.MeshPayloadOffset; TargetBlockIndex = [int]$_.TargetBlockIndex; Payload = [int]$_.DeclaredPayloadBytes; Role = [string]$_.RoleStats.PrimaryRole } })
        UvStreams = @($uvStreams | ForEach-Object { [pscustomobject]@{ MeshPayloadOffset = [int]$_.MeshPayloadOffset; TargetBlockIndex = [int]$_.TargetBlockIndex; Payload = [int]$_.DeclaredPayloadBytes; Role = [string]$_.RoleStats.PrimaryRole } })
        SideStreams = @($sideStreams | ForEach-Object { [pscustomobject]@{ MeshPayloadOffset = [int]$_.MeshPayloadOffset; TargetBlockIndex = [int]$_.TargetBlockIndex; Payload = [int]$_.DeclaredPayloadBytes; Role = [string]$_.RoleStats.PrimaryRole } })
        AttributeSetCount = $attributeSets.Count
        AttributeSummary = $attributeSummary
        ProbePath = $path
    }
}

function Format-PositionSourceStreamList {
    param([object[]] $Streams)
    $items = @($Streams | ForEach-Object { "@$($_.MeshPayloadOffset)/#$($_.TargetBlockIndex) payload=$($_.Payload) $($_.Role)" })
    if ($items.Count -eq 0) { return 'none' }
    return ($items -join ' | ')
}

function Invoke-PositionSourceSiblingRepresentativeProbeReport {
    param([Parameter(Mandatory)] [object[]] $ProbeSpecs)

    $rows = @($ProbeSpecs | ForEach-Object { New-PositionSourceRepresentativeProbeRow -Spec $_ })
    $pairSummaries = @()
    foreach ($pair in @($rows | Group-Object Pair)) {
        $pairRows = @($pair.Group | Sort-Object MeshBlock)
        if ($pairRows.Count -ne 2) {
            throw "PositionSourceSiblingRepresentativeProbeReport failed: pair '$($pair.Name)' expected exactly two probes, found $($pairRows.Count)."
        }

        $sharedPositions = @()
        foreach ($left in @($pairRows[0].PositionStreams)) {
            foreach ($right in @($pairRows[1].PositionStreams)) {
                if ([int]$left.TargetBlockIndex -eq [int]$right.TargetBlockIndex -and [int]$left.Payload -eq [int]$right.Payload) {
                    $sharedPositions += [pscustomobject]@{
                        TargetBlockIndex = [int]$left.TargetBlockIndex
                        Payload = [int]$left.Payload
                        MeshPayloadOffsets = @([int]$left.MeshPayloadOffset, [int]$right.MeshPayloadOffset)
                    }
                }
            }
        }

        if ($sharedPositions.Count -eq 0) {
            throw "PositionSourceSiblingRepresentativeProbeReport failed: pair '$($pair.Name)' has no shared position stream block/payload."
        }

        if ([int]$pairRows[0].AttributeSetCount -lt 1) {
            throw "PositionSourceSiblingRepresentativeProbeReport failed: pair '$($pair.Name)' primary mesh no longer has a complete attribute set."
        }

        if ([int]$pairRows[1].AttributeSetCount -ne 0) {
            throw "PositionSourceSiblingRepresentativeProbeReport failed: pair '$($pair.Name)' sibling mesh unexpectedly gained a complete attribute set; review before keeping the old interpretation."
        }

        $pairSummaries += [pscustomobject]@{
            Pair = [string]$pair.Name
            PairLabel = [string]$pairRows[0].PairLabel
            Id = [string]$pairRows[0].Id
            MeshBlocks = (@($pairRows | ForEach-Object { "mesh#$($_.MeshBlock)" }) -join ', ')
            MeshSizes = (@($pairRows | ForEach-Object { [string]$_.MeshSize }) -join ', ')
            SharedPositionStreams = (@($sharedPositions | ForEach-Object { "block#$($_.TargetBlockIndex) payload=$($_.Payload) offsets=$(@($_.MeshPayloadOffsets | ForEach-Object { '@' + $_ }) -join '/')" }) -join ' | ')
            PrimaryMeshSummary = "mesh#$($pairRows[0].MeshBlock) attr=$($pairRows[0].AttributeSummary); pos=$(Format-PositionSourceStreamList $pairRows[0].PositionStreams); normal=$(Format-PositionSourceStreamList $pairRows[0].NormalStreams); uv=$(Format-PositionSourceStreamList $pairRows[0].UvStreams); side=$(Format-PositionSourceStreamList $pairRows[0].SideStreams)"
            SiblingMeshSummary = "mesh#$($pairRows[1].MeshBlock) attr=$($pairRows[1].AttributeSummary); pos=$(Format-PositionSourceStreamList $pairRows[1].PositionStreams); normal=$(Format-PositionSourceStreamList $pairRows[1].NormalStreams); uv=$(Format-PositionSourceStreamList $pairRows[1].UvStreams); side=$(Format-PositionSourceStreamList $pairRows[1].SideStreams)"
            Decision = 'shared position source repeats, but sibling lacks complete attribute-set binding; candidate-only follow-up'
        }
    }

    $jsonPath = Join-Path $Out 'position-source-sibling-representative-probe-comparison.json'
    $markdownPath = Join-Path $Out 'position-source-sibling-representative-probe-comparison.md'
    $summary = [ordered]@{
        Schema = 'position-source-sibling-representative-probe-comparison/v1'
        CandidateOnly = $true
        PairSummaries = @($pairSummaries | Sort-Object Pair)
        ProbeRows = @($rows | Sort-Object Pair, MeshBlock)
        Interpretation = 'Representative parser-derived sibling probes for meshSize 305/321/329. Shared position sources are search evidence only; missing sibling attribute sets keep these below geometry/export truth.'
    }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $markdown = @(
        '# Position Source Sibling Representative Probe Comparison',
        '',
        'Candidate-only comparison of representative parser-derived sibling leads for meshSize `305`, `321`, and `329`.',
        '',
        'Generated under ignored `Exports/`; do not stage generated discovery output.',
        '',
        '| Family | ID | Meshes | Mesh sizes | Shared position | Primary mesh summary | Sibling mesh summary | Decision |',
        '|---|---|---|---|---|---|---|---|'
    )
    foreach ($pairSummary in @($pairSummaries | Sort-Object Pair)) {
        $markdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} |' -f
            (Format-WorkflowMarkdownCell $pairSummary.PairLabel),
            (Format-WorkflowMarkdownCell $pairSummary.Id),
            (Format-WorkflowMarkdownCell $pairSummary.MeshBlocks),
            (Format-WorkflowMarkdownCell $pairSummary.MeshSizes),
            (Format-WorkflowMarkdownCell $pairSummary.SharedPositionStreams),
            (Format-WorkflowMarkdownCell $pairSummary.PrimaryMeshSummary),
            (Format-WorkflowMarkdownCell $pairSummary.SiblingMeshSummary),
            (Format-WorkflowMarkdownCell $pairSummary.Decision))
    }

    $markdown += @(
        '',
        'Interpretation: these probes support source-binding search priorities only. Mesh siblings repeat the same position stream, but the sibling mesh lacks a full position+normal+UV attribute-set binding, so no role, topology, geometry, or OBJ/export truth is promoted.'
    )
    Set-Content -LiteralPath $markdownPath -Value $markdown -Encoding UTF8

    Write-Host "`n--- PositionSourceSiblingRepresentativeProbeReport candidate-only representative sibling probes" -ForegroundColor Green
    $pairSummaries | Sort-Object Pair | Select-Object PairLabel, Id, MeshBlocks, MeshSizes, SharedPositionStreams, Decision | Format-Table -AutoSize | Out-Host
    Write-Host "PositionSourceSiblingRepresentativeProbeReport JSON: $jsonPath" -ForegroundColor Green
    Write-Host "PositionSourceSiblingRepresentativeProbeReport markdown: $markdownPath" -ForegroundColor Green
    Write-Host 'PositionSourceSiblingRepresentativeProbeReport passed: representative sibling source leads stayed candidate-only.' -ForegroundColor Green
}

function Invoke-PositionSourceSiblingSecondaryProbeReport {
    param([Parameter(Mandatory)] [object[]] $ProbeSpecs)

    $rows = @($ProbeSpecs | ForEach-Object { New-PositionSourceRepresentativeProbeRow -Spec $_ })
    $pairSummaries = @()
    foreach ($pair in @($rows | Group-Object Pair)) {
        $pairRows = @($pair.Group | Sort-Object MeshBlock)
        if ($pairRows.Count -ne 2) {
            throw "PositionSourceSiblingSecondaryProbeReport failed: pair '$($pair.Name)' expected exactly two probes, found $($pairRows.Count)."
        }

        $sharedPositions = @()
        foreach ($left in @($pairRows[0].PositionStreams)) {
            foreach ($right in @($pairRows[1].PositionStreams)) {
                if ([int]$left.TargetBlockIndex -eq [int]$right.TargetBlockIndex -and [int]$left.Payload -eq [int]$right.Payload) {
                    $sharedPositions += [pscustomobject]@{
                        TargetBlockIndex = [int]$left.TargetBlockIndex
                        Payload = [int]$left.Payload
                        MeshPayloadOffsets = @([int]$left.MeshPayloadOffset, [int]$right.MeshPayloadOffset)
                    }
                }
            }
        }

        if ($sharedPositions.Count -eq 0) {
            throw "PositionSourceSiblingSecondaryProbeReport failed: pair '$($pair.Name)' has no shared position stream block/payload."
        }

        foreach ($row in $pairRows) {
            $matchingSpec = @($ProbeSpecs | Where-Object {
                [string]$_.Pair -eq [string]$row.Pair -and
                [string]$_.Id -eq [string]$row.Id -and
                [int]$_.MeshBlock -eq [int]$row.MeshBlock
            })
            if ($matchingSpec.Count -ne 1) {
                throw "PositionSourceSiblingSecondaryProbeReport failed: expected one spec for $($row.Id) mesh#$($row.MeshBlock), found $($matchingSpec.Count)."
            }

            $expectedAttributeSetCount = [int]$matchingSpec[0].ExpectedAttributeSetCount
            if ([int]$row.AttributeSetCount -ne $expectedAttributeSetCount) {
                throw "PositionSourceSiblingSecondaryProbeReport failed: $($row.Id) mesh#$($row.MeshBlock) expected $expectedAttributeSetCount complete attribute sets, found $($row.AttributeSetCount)."
            }
        }

        $pairSummaries += [pscustomobject]@{
            Pair = [string]$pair.Name
            PairLabel = [string]$pairRows[0].PairLabel
            Id = [string]$pairRows[0].Id
            MeshBlocks = (@($pairRows | ForEach-Object { "mesh#$($_.MeshBlock)" }) -join ', ')
            MeshSizes = (@($pairRows | ForEach-Object { [string]$_.MeshSize }) -join ', ')
            AttributeSetCounts = (@($pairRows | ForEach-Object { "mesh#$($_.MeshBlock)=$($_.AttributeSetCount)" }) -join ', ')
            SharedPositionStreams = (@($sharedPositions | ForEach-Object { "block#$($_.TargetBlockIndex) payload=$($_.Payload) offsets=$(@($_.MeshPayloadOffsets | ForEach-Object { '@' + $_ }) -join '/')" }) -join ' | ')
            PrimaryMeshSummary = "mesh#$($pairRows[0].MeshBlock) attr=$($pairRows[0].AttributeSummary); pos=$(Format-PositionSourceStreamList $pairRows[0].PositionStreams); normal=$(Format-PositionSourceStreamList $pairRows[0].NormalStreams); uv=$(Format-PositionSourceStreamList $pairRows[0].UvStreams); side=$(Format-PositionSourceStreamList $pairRows[0].SideStreams)"
            SiblingMeshSummary = "mesh#$($pairRows[1].MeshBlock) attr=$($pairRows[1].AttributeSummary); pos=$(Format-PositionSourceStreamList $pairRows[1].PositionStreams); normal=$(Format-PositionSourceStreamList $pairRows[1].NormalStreams); uv=$(Format-PositionSourceStreamList $pairRows[1].UvStreams); side=$(Format-PositionSourceStreamList $pairRows[1].SideStreams)"
            Decision = 'secondary sibling spot-check stayed candidate-only; attribute-set availability is evidence, not geometry truth'
        }
    }

    $jsonPath = Join-Path $Out 'position-source-sibling-secondary-probe-comparison.json'
    $markdownPath = Join-Path $Out 'position-source-sibling-secondary-probe-comparison.md'
    $summary = [ordered]@{
        Schema = 'position-source-sibling-secondary-probe-comparison/v1'
        CandidateOnly = $true
        PairSummaries = @($pairSummaries | Sort-Object Pair)
        ProbeRows = @($rows | Sort-Object Pair, MeshBlock)
        Interpretation = 'Secondary sibling-family spot checks for meshSize 305/321/329. Shared position sources remain source-binding search evidence only; observed attribute-set availability is guarded without promoting geometry/export truth.'
    }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $markdown = @(
        '# Position Source Sibling Secondary Probe Comparison',
        '',
        'Candidate-only comparison of secondary parser-derived sibling leads for meshSize `305`, `321`, and `329`.',
        '',
        'Generated under ignored `Exports/`; do not stage generated discovery output.',
        '',
        '| Family | ID | Meshes | Mesh sizes | Attribute sets | Shared position | Primary mesh summary | Sibling mesh summary | Decision |',
        '|---|---|---|---|---|---|---|---|---|'
    )
    foreach ($pairSummary in @($pairSummaries | Sort-Object Pair)) {
        $markdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} |' -f
            (Format-WorkflowMarkdownCell $pairSummary.PairLabel),
            (Format-WorkflowMarkdownCell $pairSummary.Id),
            (Format-WorkflowMarkdownCell $pairSummary.MeshBlocks),
            (Format-WorkflowMarkdownCell $pairSummary.MeshSizes),
            (Format-WorkflowMarkdownCell $pairSummary.AttributeSetCounts),
            (Format-WorkflowMarkdownCell $pairSummary.SharedPositionStreams),
            (Format-WorkflowMarkdownCell $pairSummary.PrimaryMeshSummary),
            (Format-WorkflowMarkdownCell $pairSummary.SiblingMeshSummary),
            (Format-WorkflowMarkdownCell $pairSummary.Decision))
    }

    $markdown += @(
        '',
        'Interpretation: these secondary probes check whether the representative sibling pattern repeats. They remain candidate-only because shared position streams do not by themselves prove complete position+normal+UV binding, topology truth, geometry truth, or OBJ/export readiness.'
    )
    Set-Content -LiteralPath $markdownPath -Value $markdown -Encoding UTF8

    Write-Host "`n--- PositionSourceSiblingSecondaryProbeReport candidate-only secondary sibling probes" -ForegroundColor Green
    $pairSummaries | Sort-Object Pair | Select-Object PairLabel, Id, MeshBlocks, MeshSizes, AttributeSetCounts, SharedPositionStreams, Decision | Format-Table -AutoSize | Out-Host
    Write-Host "PositionSourceSiblingSecondaryProbeReport JSON: $jsonPath" -ForegroundColor Green
    Write-Host "PositionSourceSiblingSecondaryProbeReport markdown: $markdownPath" -ForegroundColor Green
    Write-Host 'PositionSourceSiblingSecondaryProbeReport passed: secondary sibling source leads stayed candidate-only.' -ForegroundColor Green
}

function Invoke-PositionSourceSiblingExtraPositionReport {
    param([Parameter(Mandatory)] [object[]] $ProbeSpecs)

    $rows = @($ProbeSpecs | ForEach-Object { New-PositionSourceRepresentativeProbeRow -Spec $_ })
    $pairSummaries = @()
    foreach ($pair in @($rows | Group-Object Pair)) {
        $pairRows = @($pair.Group | Sort-Object MeshBlock)
        if ($pairRows.Count -ne 2) {
            throw "PositionSourceSiblingExtraPositionReport failed: pair '$($pair.Name)' expected exactly two probes, found $($pairRows.Count)."
        }

        $primary = @($pairRows | Where-Object { [int]$_.MeshBlock -eq 7 })
        $sibling = @($pairRows | Where-Object { [int]$_.MeshBlock -eq 34 })
        if ($primary.Count -ne 1 -or $sibling.Count -ne 1) {
            throw "PositionSourceSiblingExtraPositionReport failed: pair '$($pair.Name)' expected mesh#7 and mesh#34 rows."
        }

        if ([int]$primary[0].AttributeSetCount -ne 1) {
            throw "PositionSourceSiblingExtraPositionReport failed: $($primary[0].Id) mesh#7 expected one complete attribute set, found $($primary[0].AttributeSetCount)."
        }

        if ([int]$sibling[0].AttributeSetCount -ne 0) {
            throw "PositionSourceSiblingExtraPositionReport failed: $($sibling[0].Id) mesh#34 unexpectedly has complete attribute sets; review before keeping the old interpretation."
        }

        $sharedPrimaryPositions = @()
        foreach ($left in @($primary[0].PositionStreams)) {
            foreach ($right in @($sibling[0].PositionStreams)) {
                if ([int]$left.TargetBlockIndex -eq 28 -and [int]$right.TargetBlockIndex -eq 28 -and [int]$left.Payload -eq [int]$right.Payload) {
                    $sharedPrimaryPositions += [pscustomobject]@{
                        TargetBlockIndex = [int]$left.TargetBlockIndex
                        Payload = [int]$left.Payload
                        MeshPayloadOffsets = @([int]$left.MeshPayloadOffset, [int]$right.MeshPayloadOffset)
                    }
                }
            }
        }

        if ($sharedPrimaryPositions.Count -eq 0) {
            throw "PositionSourceSiblingExtraPositionReport failed: pair '$($pair.Name)' no longer shares meshSize=329 primary position stream block#28."
        }

        $extraPositionStreams = @($sibling[0].PositionStreams | Where-Object {
            [int]$_.MeshPayloadOffset -eq 304 -and
            [int]$_.TargetBlockIndex -eq 57 -and
            [string]$_.Role -eq 'position-float3-ror1-lead'
        })
        if ($extraPositionStreams.Count -ne 1) {
            throw "PositionSourceSiblingExtraPositionReport failed: $($sibling[0].Id) mesh#34 expected one extra position-like stream at @304/#57, found $($extraPositionStreams.Count)."
        }

        if (@($sibling[0].UvStreams).Count -ne 0) {
            throw "PositionSourceSiblingExtraPositionReport failed: $($sibling[0].Id) mesh#34 unexpectedly has UV stream candidates; review source-binding interpretation."
        }

        $pairSummaries += [pscustomobject]@{
            Pair = [string]$pair.Name
            PairLabel = [string]$pairRows[0].PairLabel
            Id = [string]$primary[0].Id
            SharedPrimaryPosition = (@($sharedPrimaryPositions | ForEach-Object { "block#$($_.TargetBlockIndex) payload=$($_.Payload) offsets=$(@($_.MeshPayloadOffsets | ForEach-Object { '@' + $_ }) -join '/')" }) -join ' | ')
            Mesh34ExtraPosition = (@($extraPositionStreams | ForEach-Object { "@$($_.MeshPayloadOffset)/#$($_.TargetBlockIndex) payload=$($_.Payload) $($_.Role)" }) -join ' | ')
            Mesh7Summary = "mesh#7 attr=$($primary[0].AttributeSummary); pos=$(Format-PositionSourceStreamList $primary[0].PositionStreams); normal=$(Format-PositionSourceStreamList $primary[0].NormalStreams); uv=$(Format-PositionSourceStreamList $primary[0].UvStreams); side=$(Format-PositionSourceStreamList $primary[0].SideStreams)"
            Mesh34Summary = "mesh#34 attr=$($sibling[0].AttributeSummary); pos=$(Format-PositionSourceStreamList $sibling[0].PositionStreams); normal=$(Format-PositionSourceStreamList $sibling[0].NormalStreams); uv=$(Format-PositionSourceStreamList $sibling[0].UvStreams); side=$(Format-PositionSourceStreamList $sibling[0].SideStreams)"
            Decision = 'mesh#34 extra @304/#57 position-like stream repeats; candidate-only source-binding oddity, not geometry truth'
        }
    }

    $jsonPath = Join-Path $Out 'position-source-sibling-extra-position-report.json'
    $markdownPath = Join-Path $Out 'position-source-sibling-extra-position-report.md'
    $summary = [ordered]@{
        Schema = 'position-source-sibling-extra-position-report/v1'
        CandidateOnly = $true
        PairSummaries = @($pairSummaries | Sort-Object Pair)
        ProbeRows = @($rows | Sort-Object Pair, MeshBlock)
        Interpretation = 'Focused meshSize=329 mesh#7/#34 report for the repeated mesh#34 @304/#57 position-like stream. This is source-binding search evidence only and does not promote geometry/export truth.'
    }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $markdown = @(
        '# Position Source Sibling Extra Position Report',
        '',
        'Candidate-only meshSize `329` mesh `#7/#34` report for repeated sibling mesh `#34` extra position-like stream `@304/#57`.',
        '',
        'Generated under ignored `Exports/`; do not stage generated discovery output.',
        '',
        '| ID | Shared primary position | mesh#34 extra position | mesh#7 summary | mesh#34 summary | Decision |',
        '|---|---|---|---|---|---|'
    )
    foreach ($pairSummary in @($pairSummaries | Sort-Object Pair)) {
        $markdown += ('| {0} | {1} | {2} | {3} | {4} | {5} |' -f
            (Format-WorkflowMarkdownCell $pairSummary.Id),
            (Format-WorkflowMarkdownCell $pairSummary.SharedPrimaryPosition),
            (Format-WorkflowMarkdownCell $pairSummary.Mesh34ExtraPosition),
            (Format-WorkflowMarkdownCell $pairSummary.Mesh7Summary),
            (Format-WorkflowMarkdownCell $pairSummary.Mesh34Summary),
            (Format-WorkflowMarkdownCell $pairSummary.Decision))
    }

    $markdown += @(
        '',
        'Interpretation: the repeated `@304/#57` stream is a useful source-binding clue for meshSize `329`, but mesh `#34` still lacks complete attribute-set binding. Keep this separate from residual-stream truth and do not use it for OBJ/export promotion.'
    )
    Set-Content -LiteralPath $markdownPath -Value $markdown -Encoding UTF8

    Write-Host "`n--- PositionSourceSiblingExtraPositionReport candidate-only mesh#34 extra position stream" -ForegroundColor Green
    $pairSummaries | Sort-Object Pair | Select-Object Id, SharedPrimaryPosition, Mesh34ExtraPosition, Decision | Format-Table -AutoSize | Out-Host
    Write-Host "PositionSourceSiblingExtraPositionReport JSON: $jsonPath" -ForegroundColor Green
    Write-Host "PositionSourceSiblingExtraPositionReport markdown: $markdownPath" -ForegroundColor Green
    Write-Host 'PositionSourceSiblingExtraPositionReport passed: mesh#34 extra position-like stream stayed candidate-only.' -ForegroundColor Green
}

function Invoke-PositionSourceSiblingLeadGuard {
    param([Parameter(Mandatory)] [string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "PositionSourceSiblingLeadGuard failed: report not found: $Path"
    }

    $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $groups = @((Get-JsonValueOrNull $report 'TopPositionSourceSiblings'))
    if ($groups.Count -eq 0) {
        throw 'PositionSourceSiblingLeadGuard failed: TopPositionSourceSiblings is missing or empty in mesh-binding inventory.'
    }

    function Find-PositionSourceSiblingGroup {
        param([string] $IdPrefix, [int] $TargetBlockIndex, [int] $DeclaredPayloadBytes)
        return @($groups | Where-Object {
            [string](Get-JsonValueOrDash $_ 'IdPrefix') -eq $IdPrefix -and
            [int](Get-JsonValueOrDash $_ 'TargetBlockIndex') -eq $TargetBlockIndex -and
            [int](Get-JsonValueOrDash $_ 'DeclaredPayloadBytes') -eq $DeclaredPayloadBytes
        } | Select-Object -First 1)
    }

    function Assert-PositionSourceSiblingLead {
        param(
            [string] $IdPrefix,
            [int] $TargetBlockIndex,
            [int] $DeclaredPayloadBytes,
            [int[]] $ExpectedMeshBlocks,
            [int[]] $ExpectedMeshPayloadOffsets)

        $match = @(Find-PositionSourceSiblingGroup -IdPrefix $IdPrefix -TargetBlockIndex $TargetBlockIndex -DeclaredPayloadBytes $DeclaredPayloadBytes)
        if ($match.Count -ne 1) {
            throw "PositionSourceSiblingLeadGuard failed: expected one group for $IdPrefix block#$TargetBlockIndex payload=$DeclaredPayloadBytes, found $($match.Count)."
        }

        $group = $match[0]
        if ([int](Get-JsonValueOrDash $group 'DistinctMeshBlocks') -lt 2) {
            throw "PositionSourceSiblingLeadGuard failed: $IdPrefix block#$TargetBlockIndex payload=$DeclaredPayloadBytes is no longer a sibling mesh-block group."
        }

        if ([string](Get-JsonValueOrDash $group 'Role') -ne 'position-float3-ror1-lead') {
            throw "PositionSourceSiblingLeadGuard failed: $IdPrefix block#$TargetBlockIndex payload=$DeclaredPayloadBytes role changed from position-float3-ror1-lead."
        }

        if ([string](Get-JsonValueOrDash $group 'DataStreamUsage') -ne '1' -or [string](Get-JsonValueOrDash $group 'DataStreamAccess') -ne '19') {
            throw "PositionSourceSiblingLeadGuard failed: $IdPrefix block#$TargetBlockIndex payload=$DeclaredPayloadBytes usage/access changed from 1/19."
        }

        $meshBlocks = @($group.MeshBlockIndices | ForEach-Object { [int]$_ })
        foreach ($expected in @($ExpectedMeshBlocks)) {
            if ($meshBlocks -notcontains $expected) {
                throw "PositionSourceSiblingLeadGuard failed: $IdPrefix block#$TargetBlockIndex payload=$DeclaredPayloadBytes missing mesh#$expected."
            }
        }

        $offsets = @($group.MeshPayloadOffsets | ForEach-Object { [int]$_ })
        foreach ($expected in @($ExpectedMeshPayloadOffsets)) {
            if ($offsets -notcontains $expected) {
                throw "PositionSourceSiblingLeadGuard failed: $IdPrefix block#$TargetBlockIndex payload=$DeclaredPayloadBytes missing mesh payload offset $expected."
            }
        }

        return $group
    }

    $guardGroups = @(
        (Assert-PositionSourceSiblingLead -IdPrefix 'e3de1077a37d0337' -TargetBlockIndex 24 -DeclaredPayloadBytes 852 -ExpectedMeshBlocks @(6, 30) -ExpectedMeshPayloadOffsets @(292, 296)),
        (Assert-PositionSourceSiblingLead -IdPrefix '8e01613d7ce9e297' -TargetBlockIndex 25 -DeclaredPayloadBytes 1116 -ExpectedMeshBlocks @(6, 31) -ExpectedMeshPayloadOffsets @(296))
    )

    $rows = @($groups | Sort-Object -Property @{Expression = 'Count'; Descending = $true}, IdPrefix, TargetBlockIndex | Select-Object -First 20 | ForEach-Object {
        [pscustomobject]@{
            IdPrefix = [string](Get-JsonValueOrDash $_ 'IdPrefix')
            TargetBlock = [int](Get-JsonValueOrDash $_ 'TargetBlockIndex')
            Payload = [int](Get-JsonValueOrDash $_ 'DeclaredPayloadBytes')
            Count = [int](Get-JsonValueOrDash $_ 'Count')
            DistinctMeshBlocks = [int](Get-JsonValueOrDash $_ 'DistinctMeshBlocks')
            MeshBlocks = (@($_.MeshBlockIndices | ForEach-Object { "mesh#$_" }) -join ', ')
            MeshSizes = (@($_.MeshSizes | ForEach-Object { "$(Get-JsonValueOrDash $_ 'Size'):$(Get-JsonValueOrDash $_ 'Count')" }) -join ', ')
            MeshPayloadOffsets = (@($_.MeshPayloadOffsets | ForEach-Object { "stream@$_" }) -join ', ')
            UsageAccess = "$(Get-JsonValueOrDash $_ 'DataStreamUsage')/$(Get-JsonValueOrDash $_ 'DataStreamAccess')"
            Role = [string](Get-JsonValueOrDash $_ 'Role')
        }
    })

    $jsonPath = Join-Path (Split-Path -Parent $Path) 'position-source-sibling-lead-guard.json'
    $markdownPath = Join-Path (Split-Path -Parent $Path) 'position-source-sibling-lead-guard.md'
    $summary = [ordered]@{
        Schema = 'position-source-sibling-lead-guard/v1'
        CandidateOnly = $true
        SourceReport = $Path
        TopPositionSourceSiblingGroups = $rows
        GuardedGroups = $guardGroups
        Interpretation = 'Parser-derived sibling position-source aggregation for search ranking only. It does not promote geometry truth, topology truth, or export readiness.'
    }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $markdown = @(
        '# Position Source Sibling Lead Guard',
        '',
        'Candidate-only guard over parser-derived `TopPositionSourceSiblings` from the mesh-binding inventory.',
        '',
        'Generated under ignored `Exports/`; do not stage generated discovery output.',
        '',
        '| ID | Target block | Payload | Count | Distinct meshes | Mesh blocks | Mesh sizes | Mesh offsets | Usage/access | Role |',
        '|---|---:|---:|---:|---:|---|---|---|---|---|'
    )
    foreach ($row in $rows) {
        $markdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} | {9} |' -f
            (Format-WorkflowMarkdownCell $row.IdPrefix),
            (Format-WorkflowMarkdownCell $row.TargetBlock),
            (Format-WorkflowMarkdownCell $row.Payload),
            (Format-WorkflowMarkdownCell $row.Count),
            (Format-WorkflowMarkdownCell $row.DistinctMeshBlocks),
            (Format-WorkflowMarkdownCell $row.MeshBlocks),
            (Format-WorkflowMarkdownCell $row.MeshSizes),
            (Format-WorkflowMarkdownCell $row.MeshPayloadOffsets),
            (Format-WorkflowMarkdownCell $row.UsageAccess),
            (Format-WorkflowMarkdownCell $row.Role))
    }

    $markdown += @(
        '',
        'Guarded expected groups: `e3de1077a37d0337` block `#24` payload `852`, and `8e01613d7ce9e297` block `#25` payload `1116`.',
        '',
        'Interpretation: repeated position-source blocks across sibling meshes are a parser-search clue only. Normal/UV pairing, topology proof, sane bounds, and proof guards still gate any future geometry/export promotion.'
    )
    Set-Content -LiteralPath $markdownPath -Value $markdown -Encoding UTF8

    Write-Host "`n--- PositionSourceSiblingLeadGuard parser-derived sibling source leads" -ForegroundColor Green
    $rows | Select-Object IdPrefix, TargetBlock, Payload, Count, DistinctMeshBlocks, MeshBlocks, MeshPayloadOffsets | Format-Table -AutoSize | Out-Host
    Write-Host "PositionSourceSiblingLeadGuard JSON: $jsonPath" -ForegroundColor Green
    Write-Host "PositionSourceSiblingLeadGuard markdown: $markdownPath" -ForegroundColor Green
    Write-Host 'PositionSourceSiblingLeadGuard passed: known sibling position-source leads remain candidate-only parser-search evidence.' -ForegroundColor Green
}

function Invoke-PositionSourceSiblingFamilyReport {
    param([Parameter(Mandatory)] [string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "PositionSourceSiblingFamilyReport failed: report not found: $Path"
    }

    $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $groups = @((Get-JsonValueOrNull $report 'TopPositionSourceSiblings'))
    if ($groups.Count -eq 0) {
        throw 'PositionSourceSiblingFamilyReport failed: TopPositionSourceSiblings is missing or empty in mesh-binding inventory.'
    }

    function Get-PositionSourceSiblingFamilyDecision {
        param([int] $MeshSize, [string] $MeshBlocks, [string] $MeshPayloadOffsets)

        if ($MeshSize -eq 305 -and $MeshBlocks -eq 'mesh#7, mesh#27' -and $MeshPayloadOffsets -eq 'stream@188') {
            return 'repeated meshSize=305 source-binding family; candidate-only probe queue'
        }

        if ($MeshSize -eq 321 -and $MeshBlocks -eq 'mesh#7, mesh#31' -and $MeshPayloadOffsets -eq 'stream@204') {
            return 'repeated meshSize=321 source-binding family; candidate-only probe queue'
        }

        if ($MeshSize -eq 329 -and $MeshBlocks -eq 'mesh#7, mesh#34' -and $MeshPayloadOffsets -eq 'stream@212') {
            return 'repeated meshSize=329 source-binding family; candidate-only probe queue'
        }

        if ($MeshSize -eq 325 -and $MeshBlocks -eq 'mesh#6, mesh#30') {
            return 'known shifted sibling position-source clue; candidate-only'
        }

        if ($MeshSize -eq 329 -and $MeshBlocks -eq 'mesh#6, mesh#31') {
            return 'known shifted sibling position-source clue; candidate-only'
        }

        return 'candidate-only follow-up'
    }

    $sourceRows = @()
    foreach ($group in $groups) {
        $meshSizeEntries = @((Get-JsonValueOrNull $group 'MeshSizes'))
        if ($meshSizeEntries.Count -eq 0) {
            continue
        }

        $dominantMeshSize = @($meshSizeEntries | Sort-Object -Property @{ Expression = { [int](Get-JsonValueOrDash $_ 'Count') }; Descending = $true }, @{ Expression = { [int](Get-JsonValueOrDash $_ 'Size') }; Descending = $false } | Select-Object -First 1)
        if ($dominantMeshSize.Count -ne 1) {
            continue
        }

        $meshBlocks = @((Get-JsonValueOrNull $group 'MeshBlockIndices') | ForEach-Object { [int]$_ } | Sort-Object)
        $meshPayloadOffsets = @((Get-JsonValueOrNull $group 'MeshPayloadOffsets') | ForEach-Object { [int]$_ } | Sort-Object)
        if ($meshBlocks.Count -lt 2 -or $meshPayloadOffsets.Count -eq 0) {
            continue
        }

        $sourceRows += [pscustomobject]@{
            MeshSize = [int](Get-JsonValueOrDash $dominantMeshSize[0] 'Size')
            MeshBlocks = (@($meshBlocks | ForEach-Object { "mesh#$_" }) -join ', ')
            MeshPayloadOffsets = (@($meshPayloadOffsets | ForEach-Object { "stream@$_" }) -join ', ')
            TargetBlock = [int](Get-JsonValueOrDash $group 'TargetBlockIndex')
            Payload = [int](Get-JsonValueOrDash $group 'DeclaredPayloadBytes')
            IdPrefix = [string](Get-JsonValueOrDash $group 'IdPrefix')
            Count = [int](Get-JsonValueOrDash $group 'Count')
            UsageAccess = "$(Get-JsonValueOrDash $group 'DataStreamUsage')/$(Get-JsonValueOrDash $group 'DataStreamAccess')"
            Role = [string](Get-JsonValueOrDash $group 'Role')
        }
    }

    if ($sourceRows.Count -eq 0) {
        throw 'PositionSourceSiblingFamilyReport failed: no sibling family source rows could be derived from TopPositionSourceSiblings.'
    }

    $familyRows = @($sourceRows |
        Group-Object MeshSize, MeshBlocks, MeshPayloadOffsets |
        ForEach-Object {
            $familyGroup = @($_.Group)
            $first = $familyGroup[0]
            $targetBlocks = @($familyGroup | Sort-Object TargetBlock | Select-Object -ExpandProperty TargetBlock -Unique)
            $payloads = @($familyGroup | Sort-Object Payload | Select-Object -ExpandProperty Payload -Unique)
            $ids = @($familyGroup | Sort-Object IdPrefix | Select-Object -ExpandProperty IdPrefix -Unique)
            $usageAccesses = @($familyGroup | Sort-Object UsageAccess | Select-Object -ExpandProperty UsageAccess -Unique)
            $roles = @($familyGroup | Sort-Object Role | Select-Object -ExpandProperty Role -Unique)
            $totalLinks = [int](($familyGroup | Measure-Object -Property Count -Sum).Sum)

            [pscustomobject]@{
                MeshSize = [int]$first.MeshSize
                MeshBlocks = [string]$first.MeshBlocks
                MeshPayloadOffsets = [string]$first.MeshPayloadOffsets
                EvidenceGroups = $familyGroup.Count
                TotalStreamLinks = $totalLinks
                DistinctIds = $ids.Count
                TargetBlocks = (@($targetBlocks | ForEach-Object { "block#$_" }) -join ', ')
                PayloadBytes = (@($payloads | ForEach-Object { [string]$_ }) -join ', ')
                RepresentativeIds = (@($ids | Select-Object -First 8) -join ', ')
                UsageAccess = ($usageAccesses -join ', ')
                Roles = ($roles -join ', ')
                Decision = Get-PositionSourceSiblingFamilyDecision -MeshSize ([int]$first.MeshSize) -MeshBlocks ([string]$first.MeshBlocks) -MeshPayloadOffsets ([string]$first.MeshPayloadOffsets)
            }
        } |
        Sort-Object -Property @{ Expression = 'EvidenceGroups'; Descending = $true }, @{ Expression = 'MeshSize'; Descending = $false }, MeshBlocks, MeshPayloadOffsets)

    function Assert-PositionSourceSiblingFamily {
        param(
            [int] $MeshSize,
            [string] $MeshBlocks,
            [string] $MeshPayloadOffsets,
            [int] $MinimumEvidenceGroups,
            [string] $ExpectedTargetBlocks,
            [string] $ExpectedIdPrefix = '')

        $match = @($familyRows | Where-Object {
            [int]$_.MeshSize -eq $MeshSize -and
            [string]$_.MeshBlocks -eq $MeshBlocks -and
            [string]$_.MeshPayloadOffsets -eq $MeshPayloadOffsets
        } | Select-Object -First 1)

        if ($match.Count -ne 1) {
            throw "PositionSourceSiblingFamilyReport failed: expected one family meshSize=$MeshSize $MeshBlocks $MeshPayloadOffsets, found $($match.Count)."
        }

        $row = $match[0]
        if ([int]$row.EvidenceGroups -lt $MinimumEvidenceGroups) {
            throw "PositionSourceSiblingFamilyReport failed: meshSize=$MeshSize $MeshBlocks $MeshPayloadOffsets evidence groups dropped below $MinimumEvidenceGroups (actual $($row.EvidenceGroups))."
        }

        if ([string]$row.TargetBlocks -ne $ExpectedTargetBlocks) {
            throw "PositionSourceSiblingFamilyReport failed: meshSize=$MeshSize $MeshBlocks $MeshPayloadOffsets target blocks changed from $ExpectedTargetBlocks to $($row.TargetBlocks)."
        }

        if (-not [string]::IsNullOrWhiteSpace($ExpectedIdPrefix) -and [string]$row.RepresentativeIds -notlike "*$ExpectedIdPrefix*") {
            throw "PositionSourceSiblingFamilyReport failed: meshSize=$MeshSize $MeshBlocks $MeshPayloadOffsets no longer includes expected sample $ExpectedIdPrefix."
        }

        return $row
    }

    $guardedFamilies = @(
        (Assert-PositionSourceSiblingFamily -MeshSize 329 -MeshBlocks 'mesh#7, mesh#34' -MeshPayloadOffsets 'stream@212' -MinimumEvidenceGroups 20 -ExpectedTargetBlocks 'block#28'),
        (Assert-PositionSourceSiblingFamily -MeshSize 305 -MeshBlocks 'mesh#7, mesh#27' -MeshPayloadOffsets 'stream@188' -MinimumEvidenceGroups 10 -ExpectedTargetBlocks 'block#21'),
        (Assert-PositionSourceSiblingFamily -MeshSize 321 -MeshBlocks 'mesh#7, mesh#31' -MeshPayloadOffsets 'stream@204' -MinimumEvidenceGroups 8 -ExpectedTargetBlocks 'block#25'),
        (Assert-PositionSourceSiblingFamily -MeshSize 325 -MeshBlocks 'mesh#6, mesh#30' -MeshPayloadOffsets 'stream@292, stream@296' -MinimumEvidenceGroups 1 -ExpectedTargetBlocks 'block#24' -ExpectedIdPrefix 'e3de1077a37d0337'),
        (Assert-PositionSourceSiblingFamily -MeshSize 329 -MeshBlocks 'mesh#6, mesh#31' -MeshPayloadOffsets 'stream@296' -MinimumEvidenceGroups 1 -ExpectedTargetBlocks 'block#25' -ExpectedIdPrefix '8e01613d7ce9e297')
    )

    $jsonPath = Join-Path (Split-Path -Parent $Path) 'position-source-sibling-family-report.json'
    $markdownPath = Join-Path (Split-Path -Parent $Path) 'position-source-sibling-family-report.md'
    $summary = [ordered]@{
        Schema = 'position-source-sibling-family-report/v1'
        CandidateOnly = $true
        SourceReport = $Path
        Families = $familyRows
        GuardedFamilies = $guardedFamilies
        Interpretation = 'Candidate-only cross-tab over parser-derived TopPositionSourceSiblings. Repeated sibling source families help choose probes but do not promote geometry truth or export readiness.'
    }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $markdown = @(
        '# Position Source Sibling Family Report',
        '',
        'Candidate-only family cross-tab over parser-derived `TopPositionSourceSiblings` from the mesh-binding inventory.',
        '',
        'Generated under ignored `Exports/`; do not stage generated discovery output.',
        '',
        '| Mesh size | Mesh blocks | Stream offsets | Groups | Links | IDs | Target blocks | Payload bytes | Representative IDs | Decision |',
        '|---:|---|---|---:|---:|---:|---|---|---|---|'
    )
    foreach ($row in $familyRows) {
        $markdown += ('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} | {9} |' -f
            (Format-WorkflowMarkdownCell $row.MeshSize),
            (Format-WorkflowMarkdownCell $row.MeshBlocks),
            (Format-WorkflowMarkdownCell $row.MeshPayloadOffsets),
            (Format-WorkflowMarkdownCell $row.EvidenceGroups),
            (Format-WorkflowMarkdownCell $row.TotalStreamLinks),
            (Format-WorkflowMarkdownCell $row.DistinctIds),
            (Format-WorkflowMarkdownCell $row.TargetBlocks),
            (Format-WorkflowMarkdownCell $row.PayloadBytes),
            (Format-WorkflowMarkdownCell $row.RepresentativeIds),
            (Format-WorkflowMarkdownCell $row.Decision))
    }

    $markdown += @(
        '',
        'Interpretation: repeated sibling position sources are search/ranking evidence only. Normal/UV agreement, topology/index proof, sane bounds, repeated-family proof, and proof guards still gate any future truth promotion.'
    )
    Set-Content -LiteralPath $markdownPath -Value $markdown -Encoding UTF8

    Write-Host "`n--- PositionSourceSiblingFamilyReport candidate-only family cross-tab" -ForegroundColor Green
    $familyRows | Select-Object MeshSize, MeshBlocks, MeshPayloadOffsets, EvidenceGroups, TotalStreamLinks, DistinctIds, TargetBlocks, Decision | Format-Table -AutoSize | Out-Host
    Write-Host "PositionSourceSiblingFamilyReport JSON: $jsonPath" -ForegroundColor Green
    Write-Host "PositionSourceSiblingFamilyReport markdown: $markdownPath" -ForegroundColor Green
    Write-Host 'PositionSourceSiblingFamilyReport passed: repeated sibling source families stayed candidate-only ranking evidence.' -ForegroundColor Green
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

$noBuildModes = @('DiscoveryWorkbench', 'GeneratedOutputGuard', 'SemanticHintCrossTab')
if (-not $SkipBuild -and @($Mode | Where-Object { $noBuildModes -notcontains $_ }).Count -gt 0) {
    Invoke-Checked -Label 'build' -Args @('build', $Solution, '--nologo')
}

foreach ($modeName in $Mode) {
    $entry = $commandMap[$modeName]
    $command = [string]$entry.Command
    $base = [string]$entry.Base

    if ($modeName -eq 'GeneratedOutputGuard') {
        Invoke-GeneratedOutputGuard
        continue
    }

    if ($modeName -eq 'SemanticHintCrossTab') {
        Invoke-SemanticHintCrossTab
        continue
    }

    if ($modeName -eq 'DiscoveryWorkbench') {
        Invoke-DiscoveryWorkbench
        continue
    }

    if ($modeName -eq 'ResidualPositionClusterProbeReport') {
        $clusterProbeSpecs = @(
            [pscustomobject]@{ Payload = 96; Id = '75cea2f2254e8a76'; StreamBlock = 21; MeshPayloadOffset = 188 },
            [pscustomobject]@{ Payload = 180; Id = '14924c7e9f7f03a9'; StreamBlock = 21; MeshPayloadOffset = 188 },
            [pscustomobject]@{ Payload = 192; Id = '5a4f390f196037c6'; StreamBlock = 21; MeshPayloadOffset = 188 },
            [pscustomobject]@{ Payload = 288; Id = '014e1ff60d8508f1'; StreamBlock = 21; MeshPayloadOffset = 188 },
            [pscustomobject]@{ Payload = 396; Id = 'b4de91a46cb7d4bc'; StreamBlock = 21; MeshPayloadOffset = 188 }
        )
        Invoke-ResidualPositionClusterProbeReport -ProbeSpecs $clusterProbeSpecs
        continue
    }

    if ($modeName -eq 'PositionSourceSiblingProbeReport') {
        $siblingProbeSpecs = @(
            [pscustomobject]@{ Pair = 'e3de325329'; PairLabel = 'meshSize 325/329 shifted-position sibling'; Id = 'e3de1077a37d0337'; MeshBlock = 6 },
            [pscustomobject]@{ Pair = 'e3de325329'; PairLabel = 'meshSize 325/329 shifted-position sibling'; Id = 'e3de1077a37d0337'; MeshBlock = 30 },
            [pscustomobject]@{ Pair = '8e016329'; PairLabel = 'meshSize 329 repeated-position sibling'; Id = '8e01613d7ce9e297'; MeshBlock = 6 },
            [pscustomobject]@{ Pair = '8e016329'; PairLabel = 'meshSize 329 repeated-position sibling'; Id = '8e01613d7ce9e297'; MeshBlock = 31 }
        )

        $probeSpecsWithPaths = @()
        foreach ($siblingProbe in $siblingProbeSpecs) {
            $probePath = Join-Path $Out "$base-$($siblingProbe.Id)-mesh$($siblingProbe.MeshBlock).json"
            $probeArgs = @('run', '--project', $Project, '--', $command, '--root', $Root, '--id', [string]$siblingProbe.Id, '--mesh-block', [string]$siblingProbe.MeshBlock, '--out', $probePath)
            Invoke-Checked -Label "$modeName $($siblingProbe.Id) mesh#$($siblingProbe.MeshBlock)" -Args $probeArgs
            Show-ReportSummary -ModeName 'MeshProbe' -Path $probePath
            $probeSpecsWithPaths += [pscustomobject]@{
                Pair = $siblingProbe.Pair
                PairLabel = $siblingProbe.PairLabel
                Id = $siblingProbe.Id
                MeshBlock = $siblingProbe.MeshBlock
                Path = $probePath
            }
        }

        Invoke-PositionSourceSiblingProbeReport -ProbeSpecs $probeSpecsWithPaths
        continue
    }

    if ($modeName -eq 'PositionSourceSiblingRepresentativeProbeReport') {
        $representativeProbeSpecs = @(
            [pscustomobject]@{ Pair = 'mesh305stream188'; PairLabel = 'meshSize 305 shared stream@188 sibling'; Id = '04297730afc68f38'; MeshBlock = 7 },
            [pscustomobject]@{ Pair = 'mesh305stream188'; PairLabel = 'meshSize 305 shared stream@188 sibling'; Id = '04297730afc68f38'; MeshBlock = 27 },
            [pscustomobject]@{ Pair = 'mesh321stream204'; PairLabel = 'meshSize 321 shared stream@204 sibling'; Id = '03c35c3ba518aab0'; MeshBlock = 7 },
            [pscustomobject]@{ Pair = 'mesh321stream204'; PairLabel = 'meshSize 321 shared stream@204 sibling'; Id = '03c35c3ba518aab0'; MeshBlock = 31 },
            [pscustomobject]@{ Pair = 'mesh329stream212'; PairLabel = 'meshSize 329 shared stream@212 sibling'; Id = '0364ea142bc00ce7'; MeshBlock = 7 },
            [pscustomobject]@{ Pair = 'mesh329stream212'; PairLabel = 'meshSize 329 shared stream@212 sibling'; Id = '0364ea142bc00ce7'; MeshBlock = 34 }
        )

        $probeSpecsWithPaths = @()
        foreach ($representativeProbe in $representativeProbeSpecs) {
            $probePath = Join-Path $Out "$base-$($representativeProbe.Id)-mesh$($representativeProbe.MeshBlock).json"
            $probeArgs = @('run', '--project', $Project, '--', $command, '--root', $Root, '--id', [string]$representativeProbe.Id, '--mesh-block', [string]$representativeProbe.MeshBlock, '--out', $probePath)
            Invoke-Checked -Label "$modeName $($representativeProbe.Id) mesh#$($representativeProbe.MeshBlock)" -Args $probeArgs
            Show-ReportSummary -ModeName 'MeshProbe' -Path $probePath
            $probeSpecsWithPaths += [pscustomobject]@{
                Pair = $representativeProbe.Pair
                PairLabel = $representativeProbe.PairLabel
                Id = $representativeProbe.Id
                MeshBlock = $representativeProbe.MeshBlock
                Path = $probePath
            }
        }

        Invoke-PositionSourceSiblingRepresentativeProbeReport -ProbeSpecs $probeSpecsWithPaths
        continue
    }

    if ($modeName -eq 'PositionSourceSiblingSecondaryProbeReport') {
        $secondaryProbeSpecs = @(
            [pscustomobject]@{ Pair = 'mesh329stream212secondary'; PairLabel = 'meshSize 329 secondary shared stream@212 sibling'; Id = '04de901531a091ab'; MeshBlock = 7; ExpectedAttributeSetCount = 1 },
            [pscustomobject]@{ Pair = 'mesh329stream212secondary'; PairLabel = 'meshSize 329 secondary shared stream@212 sibling'; Id = '04de901531a091ab'; MeshBlock = 34; ExpectedAttributeSetCount = 0 },
            [pscustomobject]@{ Pair = 'mesh305stream188secondary'; PairLabel = 'meshSize 305 secondary shared stream@188 sibling'; Id = '0d9a25c9a6af7b18'; MeshBlock = 7; ExpectedAttributeSetCount = 0 },
            [pscustomobject]@{ Pair = 'mesh305stream188secondary'; PairLabel = 'meshSize 305 secondary shared stream@188 sibling'; Id = '0d9a25c9a6af7b18'; MeshBlock = 27; ExpectedAttributeSetCount = 0 },
            [pscustomobject]@{ Pair = 'mesh321stream204secondary'; PairLabel = 'meshSize 321 secondary shared stream@204 sibling'; Id = '1dc433d4d2e4db64'; MeshBlock = 7; ExpectedAttributeSetCount = 1 },
            [pscustomobject]@{ Pair = 'mesh321stream204secondary'; PairLabel = 'meshSize 321 secondary shared stream@204 sibling'; Id = '1dc433d4d2e4db64'; MeshBlock = 31; ExpectedAttributeSetCount = 0 }
        )

        $probeSpecsWithPaths = @()
        foreach ($secondaryProbe in $secondaryProbeSpecs) {
            $probePath = Join-Path $Out "$base-$($secondaryProbe.Id)-mesh$($secondaryProbe.MeshBlock).json"
            $probeArgs = @('run', '--project', $Project, '--', $command, '--root', $Root, '--id', [string]$secondaryProbe.Id, '--mesh-block', [string]$secondaryProbe.MeshBlock, '--out', $probePath)
            Invoke-Checked -Label "$modeName $($secondaryProbe.Id) mesh#$($secondaryProbe.MeshBlock)" -Args $probeArgs
            Show-ReportSummary -ModeName 'MeshProbe' -Path $probePath
            $probeSpecsWithPaths += [pscustomobject]@{
                Pair = $secondaryProbe.Pair
                PairLabel = $secondaryProbe.PairLabel
                Id = $secondaryProbe.Id
                MeshBlock = $secondaryProbe.MeshBlock
                ExpectedAttributeSetCount = $secondaryProbe.ExpectedAttributeSetCount
                Path = $probePath
            }
        }

        Invoke-PositionSourceSiblingSecondaryProbeReport -ProbeSpecs $probeSpecsWithPaths
        continue
    }

    if ($modeName -eq 'PositionSourceSiblingExtraPositionReport') {
        $extraPositionProbeSpecs = @(
            [pscustomobject]@{ Pair = 'mesh329extra0364'; PairLabel = 'meshSize 329 mesh#34 extra @304/#57'; Id = '0364ea142bc00ce7'; MeshBlock = 7 },
            [pscustomobject]@{ Pair = 'mesh329extra0364'; PairLabel = 'meshSize 329 mesh#34 extra @304/#57'; Id = '0364ea142bc00ce7'; MeshBlock = 34 },
            [pscustomobject]@{ Pair = 'mesh329extra04de'; PairLabel = 'meshSize 329 mesh#34 extra @304/#57'; Id = '04de901531a091ab'; MeshBlock = 7 },
            [pscustomobject]@{ Pair = 'mesh329extra04de'; PairLabel = 'meshSize 329 mesh#34 extra @304/#57'; Id = '04de901531a091ab'; MeshBlock = 34 },
            [pscustomobject]@{ Pair = 'mesh329extra066f'; PairLabel = 'meshSize 329 mesh#34 extra @304/#57'; Id = '066fa520a8ce62e3'; MeshBlock = 7 },
            [pscustomobject]@{ Pair = 'mesh329extra066f'; PairLabel = 'meshSize 329 mesh#34 extra @304/#57'; Id = '066fa520a8ce62e3'; MeshBlock = 34 }
        )

        $probeSpecsWithPaths = @()
        foreach ($extraPositionProbe in $extraPositionProbeSpecs) {
            $probePath = Join-Path $Out "$base-$($extraPositionProbe.Id)-mesh$($extraPositionProbe.MeshBlock).json"
            $probeArgs = @('run', '--project', $Project, '--', $command, '--root', $Root, '--id', [string]$extraPositionProbe.Id, '--mesh-block', [string]$extraPositionProbe.MeshBlock, '--out', $probePath)
            Invoke-Checked -Label "$modeName $($extraPositionProbe.Id) mesh#$($extraPositionProbe.MeshBlock)" -Args $probeArgs
            Show-ReportSummary -ModeName 'MeshProbe' -Path $probePath
            $probeSpecsWithPaths += [pscustomobject]@{
                Pair = $extraPositionProbe.Pair
                PairLabel = $extraPositionProbe.PairLabel
                Id = $extraPositionProbe.Id
                MeshBlock = $extraPositionProbe.MeshBlock
                Path = $probePath
            }
        }

        Invoke-PositionSourceSiblingExtraPositionReport -ProbeSpecs $probeSpecsWithPaths
        continue
    }

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

    if ($modeName -eq 'UsageAccessCorrelationGuard') {
        $guardPath = Join-Path $Out "$base.json"
        $guardLimit = [Math]::Max($Limit, 100)
        Invoke-Checked -Label "$modeName inventory" -Args @('run', '--project', $Project, '--', $command, '--root', $Root, '--out', $guardPath, '--limit', [string]$guardLimit)
        Show-ReportSummary -ModeName 'MeshBindings' -Path $guardPath
        Invoke-UsageAccessCorrelationGuard -Path $guardPath
        continue
    }

    if ($modeName -eq 'ResidualLeadGuard') {
        $guardPath = Join-Path $Out "$base.json"
        $guardLimit = [Math]::Max($Limit, 100)
        Invoke-Checked -Label "$modeName inventory" -Args @('run', '--project', $Project, '--', $command, '--root', $Root, '--out', $guardPath, '--limit', [string]$guardLimit)
        Show-ReportSummary -ModeName 'MeshBindings' -Path $guardPath
        Invoke-ResidualLeadGuard -Path $guardPath
        continue
    }

    if ($modeName -eq 'ResidualPositionClassifierReport') {
        $reportPath = Join-Path $Out "$base.json"
        $reportLimit = [Math]::Max($Limit, 100)
        Invoke-Checked -Label "$modeName inventory" -Args @('run', '--project', $Project, '--', $command, '--root', $Root, '--out', $reportPath, '--limit', [string]$reportLimit)
        Show-ReportSummary -ModeName 'MeshBindings' -Path $reportPath
        Invoke-ResidualPositionClassifierReport -Path $reportPath
        continue
    }

    if ($modeName -eq 'PositionSourceGapReport') {
        $reportPath = Join-Path $Out "$base.json"
        $reportLimit = [Math]::Max($Limit, 100)
        Invoke-Checked -Label "$modeName inventory" -Args @('run', '--project', $Project, '--', $command, '--root', $Root, '--out', $reportPath, '--limit', [string]$reportLimit)
        Show-ReportSummary -ModeName 'MeshBindings' -Path $reportPath
        Invoke-PositionSourceGapReport -Path $reportPath
        continue
    }

    if ($modeName -eq 'PositionSourceSiblingLeadGuard') {
        $reportPath = Join-Path $Out "$base.json"
        $reportLimit = [Math]::Max($Limit, 100)
        Invoke-Checked -Label "$modeName inventory" -Args @('run', '--project', $Project, '--', $command, '--root', $Root, '--out', $reportPath, '--limit', [string]$reportLimit)
        Show-ReportSummary -ModeName 'MeshBindings' -Path $reportPath
        Invoke-PositionSourceSiblingLeadGuard -Path $reportPath
        continue
    }

    if ($modeName -eq 'PositionSourceSiblingFamilyReport') {
        $reportPath = Join-Path $Out "$base.json"
        $reportLimit = [Math]::Max($Limit, 100)
        Invoke-Checked -Label "$modeName inventory" -Args @('run', '--project', $Project, '--', $command, '--root', $Root, '--out', $reportPath, '--limit', [string]$reportLimit)
        Show-ReportSummary -ModeName 'MeshBindings' -Path $reportPath
        Invoke-PositionSourceSiblingFamilyReport -Path $reportPath
        continue
    }

    if (-not $NoSmoke) {
        $smokePath = Join-Path $Out "$base-smoke.json"
        Invoke-Checked -Label "$modeName smoke" -Args (@('run', '--project', $Project, '--', $command, '--root', $Root, '--max-total', [string]$SmokeMaxTotal, '--out', $smokePath, '--limit', [string]$Limit) + $typeArgs + $semanticCategoryArgs)
        Show-ReportSummary -ModeName $modeName -Path $smokePath
    }

    if ($Full) {
        $fullPath = Join-Path $Out "$base.json"
        Invoke-Checked -Label "$modeName full" -Args (@('run', '--project', $Project, '--', $command, '--root', $Root, '--out', $fullPath, '--limit', [string]$Limit) + $typeArgs + $semanticCategoryArgs)
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
