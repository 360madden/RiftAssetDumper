<#
.SYNOPSIS
  Thin PowerShell → Python convenience wrapper for RIFT asset workflows.

.DESCRIPTION
  Delegates to Python modules under scripts/ for all heavy lifting.
  PowerShell remains only for thin entry points and terminal convenience.
  Accepts both legacy PS mode names (MeshBindings, MeshProbe, etc.) and
  kebab-case Python names (mesh-bindings, mesh-probe, etc.).
  See docs/current-status.md for migration progress.
#>

param(
    [string] $Command = "",
    [string[]] $RemainingArgs = @()
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$PythonScript = Join-Path $ScriptDir "rift_workflow.py"

# Translation map: legacy PS mode name → kebab-case Python command name
$PSModeToKebab = @{
    'AssetSignatures' = 'asset-signatures'
    'AssetSemanticIndex' = 'asset-semantic-index'
    'MeshBindings' = 'mesh-bindings'
    'MeshProbe' = 'mesh-probe'
    'AttributeExtraProbe' = 'attribute-extra-probe'
    'AttributeExtraProofGuard' = 'attribute-extra-proof-guard'
    'AttributeExtraSiblingProofGuard' = 'attribute-extra-sibling-proof-guard'
    'UsageAccessCorrelationGuard' = 'usage-access-correlation-guard'
    'ResidualLeadGuard' = 'residual-lead-guard'
    'ResidualPositionClassifierReport' = 'residual-position-classifier-report'
    'ResidualPositionClusterProbeReport' = 'residual-position-cluster-probe-report'
    'PositionSourceGapReport' = 'position-source-gap-report'
    'PositionSourceSiblingLeadGuard' = 'position-source-sibling-lead-guard'
    'PositionSourceSiblingFamilyReport' = 'position-source-sibling-family-report'
    'PositionSourceSiblingProbeReport' = 'position-source-sibling-probe-report'
    'PositionSourceSiblingRepresentativeProbeReport' = 'position-source-sibling-representative-probe-report'
    'PositionSourceSiblingSecondaryProbeReport' = 'position-source-sibling-secondary-probe-report'
    'PositionSourceSiblingExtraPositionReport' = 'position-source-sibling-extra-position-report'
    'DiscoveryWorkbench' = 'discovery-workbench'
    'GeneratedOutputGuard' = 'generated-output-guard'
    'SemanticHintCrossTab' = 'semantic-hint-crosstab'
    'MeshStreams' = 'mesh-streams'
    'IndexCandidates' = 'index-candidates'
    'StreamEndianness' = 'stream-endianness'
    'StreamBodies' = 'stream-bodies'
    'ToolsStatus' = 'tools-status'
    'GhidraDryRun' = 'ghidra-dry-run'
    'GhidraRun' = 'ghidra-run'
    'GhidraFunctionSiteTargetGuard' = 'ghidra-function-site-target-guard'
    'GhidraFunctionSiteStatus' = 'ghidra-function-site-status'
    'GhidraFunctionSiteSurvey' = 'ghidra-function-site-survey'
    'GhidraSummarize' = 'ghidra-summarize'
    'NiDataStreamEvidenceStatus' = 'nidatastream-evidence-status'
    'NiDataStreamPromotionStatus' = 'nidatastream-promotion-status'
    'NiDataStreamPromotionDashboard' = 'nidatastream-promotion-dashboard'
    'NiDataStreamPromotionPreflight' = 'nidatastream-promotion-preflight'
    'NiDataStreamParserFieldProofGuard' = 'nidatastream-parser-field-proof-guard'
    'NiDataStreamParserExportNonConsumptionGuard' = 'nidatastream-parser-export-non-consumption-guard'
    'NiDataStreamDescriptorProofStatus' = 'nidatastream-descriptor-proof-status'
    'NiDataStreamDescriptorSampleCompare' = 'nidatastream-descriptor-sample-compare'
    'NiDataStreamDescriptorTableSample' = 'nidatastream-descriptor-table-sample'
    'GhidraPairingNonExportGuard' = 'ghidra-pairing-non-export-guard'
    'GhidraPairingReviewReport' = 'ghidra-pairing-review-report'
    'GhidraAttributeCandidateReport' = 'ghidra-attribute-candidate-report'
    'GhidraAttributeCandidateGuard' = 'ghidra-attribute-candidate-guard'
    'GhidraReviewRankProbes' = 'ghidra-review-rank-probes'
    'GhidraReviewRankProbesSummary' = 'ghidra-review-rank-probes-summary'
    'GhidraWorkflowGuardSuite' = 'ghidra-workflow-guard-suite'
    'NiDataStreamLayout' = 'nidatastream-layout'
    'All' = 'all'
}

# Translate legacy PS mode name if recognized
$PythonCommand = $Command
if ($PSModeToKebab.ContainsKey($Command)) {
    $PythonCommand = $PSModeToKebab[$Command]
}

function Invoke-PythonWorkflow {
    param([string] $Script, [string[]] $Args)
    $exitCode = 0
    & python $Script @Args 2>&1 | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) {
            Write-Host $_ -ForegroundColor Red
        } else {
            Write-Host $_
        }
        if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }
    }
    return $exitCode
}

# === Delegate to Python (GeneratedOutputGuard runs inside rift_workflow.py) ===
if ($PythonCommand) {
    Write-Host "`n==> $PythonCommand (Python)" -ForegroundColor Cyan
    $exitCode = Invoke-PythonWorkflow -Script $PythonScript -Args @($PythonCommand) + $RemainingArgs
    exit $exitCode
}
else {
    Write-Host "Usage: .\Invoke-RiftWorkflow.ps1 <command> [args...]"
    Write-Host "  Commands are handled by scripts/rift_workflow.py"
    Write-Host ""
    Write-Host "Available commands (kebab-case or legacy PS names):"
    $PSModeToKebab.GetEnumerator() | Sort-Object Name | ForEach-Object {
        Write-Host ("  {0}  (or {1})" -f $_.Value, $_.Name)
    }
}
