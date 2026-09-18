Set WshShell = CreateObject("WScript.Shell")
' Run batch file completely hidden (0 = hide window, True = wait for completion)
WshShell.Run chr(34) & Replace(WScript.ScriptFullName, "run_sync_silent.vbs", "run_sync.bat") & chr(34), 0, True
