# setup_scheduled_task.ps1
# Automates configuration of Windows Task Scheduler for the Tom Thumb Weekly Deals Tracker

param(
    [string]$TaskName = "TomThumbWeeklyDealsSync",
    [string]$SyncTime = "06:00AM",
    [switch]$IncludeUnlockTrigger = $true
)

# Check for Administrator elevation; auto-elevate if in interactive session, or print guidance
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[INFO] Elevated Administrator privileges are required to configure Task Scheduler." -ForegroundColor Yellow
    $elevated = $false
    try {
        $argList = "-ExecutionPolicy Bypass -NoProfile -File `"$PSCommandPath`""
        if ($PSBoundParameters.Count -gt 0) {
            foreach ($key in $PSBoundParameters.Keys) {
                $val = $PSBoundParameters[$key]
                if ($val -is [switch]) {
                    if ($val) { $argList += " -$key" }
                } else {
                    $argList += " -$key `"$val`""
                }
            }
        }
        $proc = Start-Process powershell.exe -ArgumentList $argList -Verb RunAs -PassThru -Wait -ErrorAction Stop
        $elevated = $true
        exit $proc.ExitCode
    } catch {
        Write-Warning "Could not automatically elevate via UAC from background session: $_"
        Write-Host "Please run the following command in an Administrator PowerShell window:" -ForegroundColor Cyan
        Write-Host "  powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`"`n" -ForegroundColor Green
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$vbsPath = Join-Path $scriptDir "run_sync_silent.vbs"

if (-not (Test-Path $vbsPath)) {
    Write-Error "Launcher script not found: $vbsPath"
    exit 1
}

Write-Host "Configuring Task Scheduler for '$TaskName'..." -ForegroundColor Cyan
Write-Host "Script Directory: $scriptDir"
Write-Host "Weekly Scheduled Time: Every Wednesday at $SyncTime"

# Action: Run VBScript via wscript.exe (silent, no command prompt popup)
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbsPath`"" -WorkingDirectory $scriptDir

# Primary Trigger: Weekly on Wednesday at specified time (when new circulars drop)
$weeklyTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday -At $SyncTime
$triggers = @($weeklyTrigger)

# Secondary Trigger: Workstation unlock (ConsoleUnlock)
if ($IncludeUnlockTrigger) {
    try {
        $unlockTrigger = Get-CimClass -ClassName MSFT_TaskSessionStateChangeTrigger -Namespace Root/Microsoft/Windows/TaskScheduler | New-CimInstance -ClientOnly
        $unlockTrigger.StateChange = 8 # 8 = ConsoleUnlock
        $unlockTrigger.Enabled = $true
        $unlockTrigger.Delay = "PT30S"  # 30-second delay after unlock so network & DNS stack stabilize
        $triggers += $unlockTrigger
        Write-Host "Added Workstation Unlock trigger (with 30s stabilization delay)." -ForegroundColor Gray
    } catch {
        Write-Warning "Could not configure Workstation Unlock trigger: $_"
    }
}

# Task Settings:
# - WakeToRun:$false: Do NOT wake a closed laptop during Modern Standby (prevents 0-second aborts)
# - StartWhenAvailable: Catch up missed runs immediately when the laptop wakes / opens
# - StopOnIdleEnd:$false: Never terminate when user touches mouse or keyboard
# - AllowStartIfOnBatteries: Run even on battery power
# - DontStopIfGoingOnBatteries: Keep running if disconnected from charger
# - ExecutionTimeLimit: 1-hour execution limit
# - MultipleInstances IgnoreNew: Prevent concurrent executions
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun:$false `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

$settings.IdleSettings.StopOnIdleEnd = $false

# Principal: Interactive logon session of current user
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "`n[SUCCESS] Scheduled task '$TaskName' registered successfully!" -ForegroundColor Green
    Write-Host "  - Schedule: Weekly every Wednesday at $SyncTime"
    if ($IncludeUnlockTrigger) {
        Write-Host "  - Unlock Trigger: Enabled (runs 30s after unlocking PC)"
    }
    Write-Host "  - Wake on sleep: Disabled (avoids Modern Standby closed-lid aborts)"
    Write-Host "  - Catch-up missed runs: Enabled (runs when you open/unlock PC if schedule was missed)"
    Write-Host "  - Stop on idle end: Disabled (user mouse/keyboard input will not abort running task)"
    Write-Host "  - Action: Runs silently in background and logs to 'logs\weekly_deals_task.log'"
    Write-Host "`nTo test run the task immediately, run:" -ForegroundColor Yellow
    Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
} catch {
    Write-Host "`n[ERROR] Failed to register task: $_" -ForegroundColor Red
    Write-Host "Tip: Try running PowerShell as Administrator if permission is denied."
}
