$ErrorActionPreference = 'Stop'
$syncRepoRoot = Split-Path -Parent $PSScriptRoot
$syncPython = (Get-Command python -ErrorAction Stop).Source
$syncPythonWindowless = Join-Path (Split-Path -Parent $syncPython) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $syncPythonWindowless)) {
    throw 'pythonw.exe was not found beside Python. Install Python for this user first.'
}
$syncUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$syncScriptPath = Join-Path $PSScriptRoot 'sync_usage.py'
$syncTaskName = 'NanCyBlog-UsageSync'
$syncExisting = Get-ScheduledTask -TaskName $syncTaskName -ErrorAction SilentlyContinue
if ($syncExisting -and $syncExisting.Actions.Arguments -notcontains ('"' + $syncScriptPath + '" --publish')) {
    throw 'A task with this name points to another checkout. Inspect it before replacing it.'
}
$syncAction = New-ScheduledTaskAction -Execute $syncPythonWindowless -Argument ('"' + $syncScriptPath + '" --publish') -WorkingDirectory $syncRepoRoot
$syncTriggers = @(
    (New-ScheduledTaskTrigger -AtLogOn -User $syncUser),
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(30) -RepetitionInterval (New-TimeSpan -Minutes 30))
)
$syncPrincipal = New-ScheduledTaskPrincipal -UserId $syncUser -LogonType Interactive -RunLevel Limited
$syncSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $syncTaskName -Action $syncAction -Trigger $syncTriggers -Principal $syncPrincipal -Settings $syncSettings -Description 'Read local ChatGPT token activity and publish a statistics-only snapshot to NanCy blog every 30 minutes while signed in.' -Force | Out-Null
Get-ScheduledTask -TaskName $syncTaskName | Select-Object TaskName, State
