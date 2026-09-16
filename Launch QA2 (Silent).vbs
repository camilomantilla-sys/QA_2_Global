' Arranca QA2 sin ventana, y avisa si no arranco.
'
' Antes esto lanzaba el .bat oculto y no volvia a mirar. Si algo
' fallaba -- y sin ventana todo falla en silencio -- la persona se
' quedaba esperando. Una companera de Camilo espero diez minutos a un
' navegador que no iba a abrirse nunca.
'
' Y el mensaje de "primera vez" salia mirando si existe .venv, que es
' cosa de una copia de desarrollo. El paquete que recibe el equipo no
' tiene .venv: tiene python\ con su interprete dentro y no hay nada
' que instalar. Se anunciaba un minuto de espera que no existia.
Option Explicit

Dim fso, shell, scriptDir, launcherPath, esPaquete, errorFile
Dim intentos, arrancado, url

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
launcherPath = scriptDir & "\run_qa2_silent.bat"
url = "http://localhost:8501"
errorFile = shell.ExpandEnvironmentStrings("%TEMP%") & "\qa2_launch_error.txt"

If Not fso.FileExists(launcherPath) Then
    MsgBox "No encuentro run_qa2_silent.bat junto a este archivo." & vbCrLf & _
           vbCrLf & _
           "Este lanzador tiene que quedarse dentro de la carpeta de " & _
           "QA2, al lado de run_qa2_silent.bat y de la carpeta ui. " & _
           "Si descargaste solo este archivo suelto, vuelve a " & _
           "descargar la carpeta entera.", 16, "QA2 - no puede arrancar"
    WScript.Quit
End If

' El paquete trae su propio Python. Una copia de desarrollo no, y ahi
' si hay un minuto de instalacion que vale la pena anunciar.
esPaquete = fso.FileExists(scriptDir & "\python\python.exe")

If Not esPaquete And Not fso.FolderExists(scriptDir & "\.venv") Then
    MsgBox "Preparando QA2 por primera vez -- puede tardar un minuto." & vbCrLf & _
           vbCrLf & _
           "Pulsa Aceptar y espera: QA2 se abrira solo en tu " & _
           "navegador cuando este listo.", 64, "QA2"
End If

shell.CurrentDirectory = scriptDir
shell.Run """" & launcherPath & """", 0, False

' Esperar a que responda. Un paquete arranca en segundos; una copia de
' desarrollo que tiene que instalar sus librerias tarda bastante mas.
arrancado = False
For intentos = 1 To 180
    WScript.Sleep 1000
    If Responde(url) Then
        arrancado = True
        Exit For
    End If
    If fso.FileExists(errorFile) Then Exit For
Next

If arrancado Then
    shell.Run url, 1, False
    WScript.Quit
End If

' No arranco. Decir lo que se sepa, que es mejor que nada.
Dim motivo, contenido
motivo = ""
If fso.FileExists(errorFile) Then
    On Error Resume Next
    contenido = fso.OpenTextFile(errorFile, 1).ReadAll()
    On Error GoTo 0
    If InStr(contenido, "NO_PYTHON") > 0 Then
        motivo = "Esta carpeta es una copia del proyecto y necesita " & _
                 "Python instalado, que no esta." & vbCrLf & vbCrLf & _
                 "El paquete que reparte el equipo no lo necesita: " & _
                 "trae el suyo. Pide ese."
    End If
End If

If motivo = "" And esPaquete Then
    motivo = "El paquete parece incompleto. Si al extraer el .zip " & _
             "salio algun error, vuelve a extraerlo: puede que " & _
             "falten archivos." & vbCrLf & vbCrLf & _
             "En PowerShell, dentro de la carpeta del .zip:" & vbCrLf & _
             "    tar -xf ""QA2-...-windows.zip"""
End If

If motivo = "" Then
    motivo = "QA2 no respondio en tres minutos."
End If

MsgBox motivo & vbCrLf & vbCrLf & _
       "Para ver el error completo, abre run_qa2.bat en vez de este " & _
       "archivo: ese deja una ventana con lo que paso.", _
       48, "QA2 - no arranco"

Function Responde(direccion)
    Dim http
    Responde = False
    On Error Resume Next
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.Open "GET", direccion, False
    http.Send
    If Err.Number = 0 Then
        If http.Status >= 200 And http.Status < 500 Then Responde = True
    End If
    Err.Clear
    On Error GoTo 0
End Function
