Set-Location (Join-Path $PSScriptRoot '..')
Write-Warning 'LAN bridge uses HTTP. Use trusted private Wi-Fi only; never port-forward TCP 8765.'
$env:JARVIS_BRIDGE_HOST = '0.0.0.0'
$env:JARVIS_BRIDGE_ALLOW_LAN_HTTP = '1'
if (Test-Path 'venv\Scripts\python.exe') { & '.\venv\Scripts\python.exe' '.\android_bridge.py' } else { & py -3 '.\android_bridge.py' }
