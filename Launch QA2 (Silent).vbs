' Test launcher: starts QA2 with no visible terminal window and lets
' Streamlit open your browser automatically, same as run_qa2.bat but
' hidden. Double-click this file to start QA2.
'
' To stop QA2 afterwards, double-click "Stop QA2.vbs" -- there's no
' window to close since this one is silent.
Option Explicit

Dim fso, shell, scriptDir, venvPath

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")

venvPath = scriptDir & "\.venv"

If Not fso.FolderExists(venvPath) Then
    MsgBox "Setting up QA2 for the first time -- this can take a minute." & vbCrLf & _
           vbCrLf & _
           "Click OK, then wait: QA2 will open in your browser " & _
           "automatically once it's ready.", 64, "QA2"
End If

shell.CurrentDirectory = scriptDir
shell.Run """" & scriptDir & "\run_qa2_silent.bat""", 0, False
