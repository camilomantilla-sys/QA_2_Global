' Test launcher: starts QA2 with no visible terminal window and lets
' Streamlit open your browser automatically, same as run_qa2.bat but
' hidden. Double-click this file to start QA2.
'
' To stop QA2 afterwards, double-click "Stop QA2.vbs" -- there's no
' window to close since this one is silent.
Option Explicit

Dim fso, shell, scriptDir, venvPath, launcherPath

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")

launcherPath = scriptDir & "\run_qa2_silent.bat"

If Not fso.FileExists(launcherPath) Then
    MsgBox "Can't find run_qa2_silent.bat next to this file." & vbCrLf & _
           vbCrLf & _
           "This launcher needs to stay inside the QA2 project " & _
           "folder, alongside run_qa2_silent.bat, requirements.txt " & _
           "and the ui/ folder -- if you copied or downloaded just " & _
           "this .vbs file on its own (e.g. from a SharePoint link " & _
           "to this single file), move it back into that folder, " & _
           "or share/download the whole project folder instead.", _
           16, "QA2 -- can't start"
    WScript.Quit
End If

venvPath = scriptDir & "\.venv"

If Not fso.FolderExists(venvPath) Then
    MsgBox "Setting up QA2 for the first time -- this can take a minute." & vbCrLf & _
           vbCrLf & _
           "Click OK, then wait: QA2 will open in your browser " & _
           "automatically once it's ready.", 64, "QA2"
End If

shell.CurrentDirectory = scriptDir
shell.Run """" & scriptDir & "\run_qa2_silent.bat""", 0, False
