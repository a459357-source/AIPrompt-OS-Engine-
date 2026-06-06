' 安装桌面快捷方式 — 双击运行一次即可
' 之后从桌面双击 "Prompt OS Galgame" 图标启动游戏

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
strDesktop = objShell.SpecialFolders("Desktop")
strShortcut = strDesktop & "\Prompt OS Galgame.lnk"
strTarget = strDir & "\启动.vbs"
strIcon = strDir & "\prompt-os-engine.ico"

' 如果图标不存在，用通用图标
If Not objFSO.FileExists(strIcon) Then
    strIcon = "shell32.dll"
End If

Set objLink = objShell.CreateShortcut(strShortcut)
objLink.TargetPath = strTarget
objLink.WorkingDirectory = strDir
objLink.IconLocation = strIcon
objLink.Description = "Prompt OS Galgame — AI 互动叙事引擎"
objLink.Save

MsgBox "桌面快捷方式已创建！" & vbCrLf & vbCrLf & _
       "双击桌面上的 ""Prompt OS Galgame"" 即可启动游戏。", 64, "安装完成"
