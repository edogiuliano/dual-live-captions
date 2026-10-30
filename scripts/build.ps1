param([switch]$SkipTests, [string]$Version = '')
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
Set-Location -LiteralPath $projectRoot
$applicationVersion = (& $pythonPath -c "import sys; sys.path.insert(0, 'src'); from dual_live_captions import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not read the application version.' }
if ($Version -and $Version -ne $applicationVersion) { throw 'Build version must match the application version.' }
$Version = $applicationVersion
if (-not $SkipTests) {
    & $pythonPath -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
}
& $pythonPath scripts\packaging\make_icon.py
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
$versionInfo = Join-Path $projectRoot ('build\' + $Version + '\windows-version.txt')
& $pythonPath scripts\packaging\make_version_info.py $versionInfo
if ($LASTEXITCODE -ne 0) { throw 'Windows version metadata generation failed.' }
$buildOptions = @()
if ($Version) {
    if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid release version' }
    $buildOptions = @('--distpath', (Join-Path $projectRoot ('dist\' + $Version)), '--workpath', (Join-Path $projectRoot ('build\' + $Version)))
}
& $pythonPath -m PyInstaller --noconfirm --clean --windowed --onedir --name DualLiveCaptions --optimize 1 --icon assets\app.ico --version-file $versionInfo --paths src --collect-all faster_whisper --collect-all ctranslate2 --collect-all lingua --copy-metadata faster-whisper --copy-metadata ctranslate2 --copy-metadata onnxruntime --copy-metadata PyAudioWPatch --copy-metadata soxr --copy-metadata PySide6-Essentials --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module PySide6.QtPdf --exclude-module torch --exclude-module pytest --add-data 'assets;assets' @buildOptions scripts\launch.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
$destination = Join-Path $projectRoot 'dist\DualLiveCaptions'
if ($Version) { $destination = Join-Path $projectRoot ('dist\' + $Version + '\DualLiveCaptions') }
Copy-Item -LiteralPath (Join-Path $projectRoot 'README.md') -Destination $destination
Copy-Item -LiteralPath (Join-Path $projectRoot 'LICENSE') -Destination $destination
Copy-Item -LiteralPath (Join-Path $projectRoot 'docs') -Destination $destination -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'install-portable.ps1') -Destination $destination
& $pythonPath scripts\packaging\collect_licenses.py --destination (Join-Path $destination 'THIRD_PARTY')
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
$shortcutPath = Join-Path $projectRoot 'Dual Live Captions.lnk'
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $destination 'DualLiveCaptions.exe'
$shortcut.WorkingDirectory = $destination
$shortcut.IconLocation = $shortcut.TargetPath
$shortcut.Save()
Get-FileHash -LiteralPath (Join-Path $destination 'DualLiveCaptions.exe') -Algorithm SHA256 | Format-List
