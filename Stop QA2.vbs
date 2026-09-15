' Detiene QA2, corra en el puerto que corra.
'
' Antes esto mataba lo que escuchara en el 8501 y nada mas, y de ahi
' salia una bola de nieve: si el 8501 seguia ocupado por una sesion
' anterior, Streamlit arrancaba en el 8502, y "Stop" mataba el 8501 --
' que ya no era el suyo. Cada vuelta dejaba un proceso mas. Camilo
' llego a once, y con ellos vivos Windows no deja borrar la carpeta de
' QA2 porque sus archivos estan en uso.
'
' Ahora se buscan por lo que ejecutan, no por donde escuchan: solo los
' python que corren el app_v2 de QA2. Otro Python que alguien tenga
' abierto no se toca.
Option Explicit

Dim wmi, procesos, p, cmd, muertos, fallidos
muertos = 0
fallidos = 0

Set wmi = GetObject("winmgmts:{impersonationLevel=impersonate}!\\.\root\cimv2")
Set procesos = wmi.ExecQuery( _
    "SELECT ProcessId, CommandLine FROM Win32_Process " & _
    "WHERE Name = 'python.exe' OR Name = 'pythonw.exe'")

For Each p In procesos
    cmd = LCase("" & p.CommandLine)
    If InStr(cmd, "streamlit") > 0 And InStr(cmd, "app_v2") > 0 Then
        On Error Resume Next
        p.Terminate()
        If Err.Number = 0 Then
            muertos = muertos + 1
        Else
            fallidos = fallidos + 1
        End If
        Err.Clear
        On Error GoTo 0
    End If
Next

If muertos = 0 And fallidos = 0 Then
    MsgBox "QA2 no estaba corriendo.", 64, "QA2"
ElseIf fallidos = 0 Then
    If muertos = 1 Then
        MsgBox "QA2 se detuvo.", 64, "QA2"
    Else
        MsgBox "Se detuvieron " & muertos & " instancias de QA2." & vbCrLf & _
               vbCrLf & _
               "Habia mas de una abierta. Pasa cuando se cierra la " & _
               "ventana sin detenerlo: el proceso sigue vivo y la " & _
               "siguiente vez QA2 arranca en otro puerto.", 64, "QA2"
    End If
Else
    MsgBox "Se detuvieron " & muertos & ", y " & fallidos & " no se " & _
           "dejaron." & vbCrLf & vbCrLf & _
           "Abre el Administrador de tareas y termina los python.exe " & _
           "que queden.", 48, "QA2"
End If
