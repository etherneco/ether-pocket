# Install the signed matching driver obtained from Microsoft Update Catalog.
# This changes only Windows USB driver binding, not phone partitions.
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$driverRoot = Join-Path $workspaceRoot 'tools\usb-driver\catalog-google'
$logPath = Join-Path $workspaceRoot 'evidence\fastboot-driver-install.txt'
$catalogPath = Join-Path $driverRoot 'androidwinusb.cat'
$infPath = Join-Path $driverRoot 'android_winusb.inf'
try {
    $signature = Get-AuthenticodeSignature -LiteralPath $catalogPath
    if ($signature.Status -ne 'Valid') { throw 'Driver catalog signature is not valid.' }
    if (-not (Select-String -LiteralPath $infPath -SimpleMatch 'USB\VID_18D1&PID_D00D')) {
        throw 'Driver does not list the connected Fastboot hardware ID.'
    }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Driver installation requires Windows administrator privileges.'
    }
    & "$env:SystemRoot\System32\pnputil.exe" /add-driver $infPath /install 2>&1 |
        Set-Content -LiteralPath $logPath
    $driverExitCode = $LASTEXITCODE
    Add-Content -LiteralPath $logPath -Value "ExitCode=$driverExitCode"
    exit $driverExitCode
} catch {
    $_ | Out-String | Set-Content -LiteralPath $logPath
    exit 1
}
