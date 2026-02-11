$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$sc = $ws.CreateShortcut("$desktop\CLAUDE D.lnk")
$sc.TargetPath = "C:\Projects\Clawdbot\launch_claude_memory.bat"
$sc.WorkingDirectory = "C:\Projects\Clawdbot"
$sc.Description = "Launch Claude Code with Memory System"
$sc.IconLocation = "C:\Users\David\AppData\Local\AnthropicClaude\claude.exe,0"
$sc.Save()
Write-Host "Shortcut created at: $desktop\Claude Memory.lnk"
