param([Parameter(Mandatory=$true)][ValidateSet('Android','Mobian')][string]$System)
$ErrorActionPreference = 'Stop'
$pythonTool = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (!(Test-Path -LiteralPath $pythonTool)) { throw 'The configured Python runtime is missing.' }
& $pythonTool (Join-Path $PSScriptRoot 'switch-etherpocket.py') $System
if ($LASTEXITCODE -ne 0) { throw "System switch did not finish: exit code $LASTEXITCODE" }
