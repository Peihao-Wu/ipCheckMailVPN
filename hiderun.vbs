Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("WScript.Shell")

' 获取当前脚本的路径
currentDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' 设置要运行的批处理文件路径
batFile = currentDir & "\run.bat"

' 运行批处理文件
objShell.Run batFile, 0, False
