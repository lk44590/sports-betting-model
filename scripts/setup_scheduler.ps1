# PowerShell script to set up Windows Task Scheduler for daily runs
# Run this as Administrator

$Action = New-ScheduledTaskAction -Execute "python" -Argument "daily_run.py" -WorkingDirectory "$PSScriptRoot"

$Trigger = New-ScheduledTaskTrigger -Daily -At "10:00AM"

$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -IdleDuration 00:10:00

$Task = New-ScheduledTask -Action $Action -Trigger $Trigger -Settings $Settings

Register-ScheduledTask -TaskName "SportsBetting-DailyPicks" -InputObject $Task -Force

Write-Host "Task 'SportsBetting-DailyPicks' scheduled for daily at 10:00 AM"
Write-Host "To remove: Unregister-ScheduledTask -TaskName 'SportsBetting-DailyPicks' -Confirm:$false"
