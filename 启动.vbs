' Prompt OS Galgame Launcher v2
' Double-click to start - no console, no setup needed

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

' --- Start server ---
objShell.Run "python engine\run.py --mode web", 0, False

' --- Wait for server ---
WScript.Sleep 3000

' --- Open browser ---
objShell.Run "http://127.0.0.1:8000"
