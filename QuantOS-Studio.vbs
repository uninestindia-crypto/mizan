' ==============================================================================
' QuantOS Studio — Windows Zero-Console Desktop Launcher
' Unsloth Studio-style clean desktop entrypoint for non-technical users.
' Launches QuantOS Studio without opening any black terminal/command prompt box.
' ==============================================================================
Set FSO = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' 1. Locate pythonw.exe (.venv first, then system PATH)
VenvPythonw = ScriptDir & "\.venv\Scripts\pythonw.exe"
QuantosStudioPy = ScriptDir & "\quantos_studio.py"

If FSO.FileExists(VenvPythonw) Then
    PythonExe = VenvPythonw
Else
    PythonExe = "pythonw.exe"
End If

' 2. Execute silently with hidden window (WindowStyle = 0)
CmdLine = """" & PythonExe & """ """ & QuantosStudioPy & """"
WshShell.CurrentDirectory = ScriptDir
WshShell.Run CmdLine, 0, False

Set WshShell = Nothing
Set FSO = Nothing
