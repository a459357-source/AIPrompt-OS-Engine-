' Prompt OS Galgame Launcher v2
' Starts server in background, opens splash screen that auto-connects

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strDir

' --- Check Python ---
On Error Resume Next
objShell.Run "%comspec% /c python --version", 0, True
hasPython = (Err.Number = 0)
On Error Goto 0

If Not hasPython Then
    MsgBox "Python not found!" & vbCrLf & vbCrLf & _
           "Please install Python 3.10+ from python.org", 48, "Prompt OS Galgame"
    WScript.Quit 1
End If

' --- Install deps ---
objShell.Run "%comspec% /c pip install -r requirements.txt --quiet", 0, True

' --- Start server (hidden) ---
objShell.Run "python engine\run.py --mode web", 0, False

' --- Open splash screen immediately ---
objShell.Run """" & strDir & "\启动.html"""
