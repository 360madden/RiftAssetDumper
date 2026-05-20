<#
.SYNOPSIS
  Thin PowerShell → Python convenience wrapper for RIFT asset workflows.

.DESCRIPTION
  Delegates to Python modules under scripts/ for all heavy lifting.
  PowerShell remains only for thin entry points and terminal convenience.
  See docs/current-status.md for migration progress.
#>

param(
    [string] $Command = "",
    [string[]] $RemainingArgs = @()
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$PythonScript = Join-Path $ScriptDir "rift_workflow.py"

function Invoke-PythonWorkflow {
    param([string] $Script, [string[]] $Args)
    $pyCmd = @("python", $Script) + $Args
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

# === Generated output safety guard (Python) ===
Write-Host "`n--- GeneratedOutputGuard (Python)" -ForegroundColor Cyan
$guardResult = & python -c @"
import sys; sys.path.insert(0, '$RepoRoot')
from scripts.rift_workflow_utils import generated_output_guard
generated_output_guard()
"@ 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host $guardResult -ForegroundColor Red
    throw "GeneratedOutputGuard failed (Python)."
}
Write-Host $guardResult

# === Delegate workflow command to Python ===
if ($Command) {
    Write-Host "`n==> $Command (Python)" -ForegroundColor Cyan
    $exitCode = Invoke-PythonWorkflow -Script $PythonScript -Args @($Command) + $RemainingArgs
    exit $exitCode
}
else {
    Write-Host "Usage: .\Invoke-RiftWorkflow.ps1 <command> [args...]"
    Write-Host "  Commands are handled by scripts/rift_workflow.py"
}
