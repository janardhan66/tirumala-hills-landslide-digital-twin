param(
    [string]$PythonPath = (Join-Path $PSScriptRoot "..\venv\Scripts\python.exe"),
    [string]$TaskName = "TirumalaLandslideMonitoring"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExecutable = (Resolve-Path $PythonPath).Path
$schedulerScript = Join-Path $projectRoot "automation\scheduler.py"
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path $schedulerScript -PathType Leaf)) {
    throw "Scheduler entry point not found: $schedulerScript"
}

$action = New-ScheduledTaskAction `
    -Execute $pythonExecutable `
    -Argument "`"$schedulerScript`" start" `
    -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Starts the Tirumala Hills monitoring scheduler when this user signs in." `
    -Force | Out-Null

Write-Host "Registered '$TaskName' for user $userId. It starts when you sign in."
