Set-Location (Join-Path $PSScriptRoot '..')
if (Test-Path 'venv\\Scripts\\python.exe') { & '.\\venv\\Scripts\\python.exe' '.\\android_bridge.py' } else { & py -3 '.\\android_bridge.py' }
