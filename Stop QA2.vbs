' Stops the QA2 server started by "Launch QA2 (Silent).vbs". Needed
' because the silent launcher has no window to close -- this finds
' whatever process is listening on QA2's port (8501) and ends it.
' Double-click this file when you're done using QA2.
Option Explicit

Dim shell
Set shell = CreateObject("WScript.Shell")

shell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr "":8501"" ^| findstr LISTENING') do taskkill /F /PID %a", 0, True

MsgBox "QA2 has been stopped.", 64, "QA2"
