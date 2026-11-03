$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    python -m unittest discover -s etherpocket-control -p test_transport.py
    if ($LASTEXITCODE -ne 0) { throw 'Transport tests failed' }
    $agentData = (Join-Path $PSScriptRoot 'agent.py') + ';.'
    python -m PyInstaller --noconfirm --windowed --onedir --name EtherPocketControl --distpath build/windows --workpath build/windows-work --specpath build --add-data $agentData etherpocket-control/app.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows build failed' }
    $appDir = Join-Path $projectRoot 'build/windows/EtherPocketControl'
    @{
        host = '10.77.0.2'
        key = Join-Path $projectRoot 'build/etherpocket_ed25519'
        known_hosts = Join-Path $projectRoot 'build/mobian-known-hosts'
        fps = 8
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $appDir 'connection.json') -Encoding utf8
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.txt') -Destination $appDir
    $shortcutFolders = @(
        [Environment]::GetFolderPath('Desktop')
        [Environment]::GetFolderPath('Programs')
    )
    $shortcutShell = New-Object -ComObject WScript.Shell
    foreach ($shortcutFolder in $shortcutFolders) {
        $shortcut = $shortcutShell.CreateShortcut((Join-Path $shortcutFolder 'EtherPocket Control.lnk'))
        $shortcut.TargetPath = Join-Path $appDir 'EtherPocketControl.exe'
        $shortcut.WorkingDirectory = $appDir
        $shortcut.Description = 'Podgląd i sterowanie EtherPocket przez USB'
        $shortcut.Save()
    }
    Write-Output (Join-Path $appDir 'EtherPocketControl.exe')
} finally {
    Pop-Location
}
