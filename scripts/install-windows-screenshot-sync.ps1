$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = (& python -c 'import sys; print(sys.executable)').Trim()
if ($LASTEXITCODE -ne 0) { throw 'Python 3 is required' }
$pythonwPath = Join-Path (Split-Path -Parent $pythonPath) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonwPath)) { throw 'pythonw.exe not found' }
$syncScript = Join-Path $PSScriptRoot 'windows-screenshot-sync.py'
foreach ($required in @('build/etherpocket_ed25519', 'build/mobian-known-hosts')) {
    if (-not (Test-Path -LiteralPath (Join-Path $taskRoot $required))) { throw "Missing $required" }
}
# Startup shortcut runs hidden for this user, without administrator privileges.
$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'EtherPocket Screenshot Sync.lnk'
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonwPath
$shortcut.Arguments = '"' + $syncScript + '"'
$shortcut.WorkingDirectory = $taskRoot
$shortcut.WindowStyle = 7
$shortcut.Description = 'Copy phone screenshots to E:\Pictures\Screenshots over USB SSH'
$shortcut.Save()
Start-Process -FilePath $pythonwPath -ArgumentList ('"' + $syncScript + '"') -WindowStyle Hidden
Write-Output "Enabled screenshot copying now and at Windows login: $shortcutPath"
