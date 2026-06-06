' Prompt OS Galgame Runtime — 一键启动（无黑窗）
' 双击此文件 → 自动启动服务器 → 自动打开浏览器
' 需要停止时：点击游戏页面底部红色 ⏻ 按钮关闭服务器

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' 脚本所在目录作为工作目录
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strDir

' 检查 Python 是否可用
On Error Resume Next
objShell.Run "python --version", 0, True
If Err.Number <> 0 Then
    MsgBox "未找到 Python，请先安装 Python 3.10+", 48, "Prompt OS Galgame"
    WScript.Quit 1
End If
On Error Goto 0

' 启动服务器（隐藏窗口）
objShell.Run "python engine\run.py --mode web", 0, False

' 等服务器就绪
WScript.Sleep 2500

' 打开浏览器
objShell.Run "http://127.0.0.1:8000"
