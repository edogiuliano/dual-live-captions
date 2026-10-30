param([string]$Destination = (Join-Path $env:LOCALAPPDATA 'Programs\DualLiveCaptions'))
$ErrorActionPreference = 'Stop'
$source = $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $source 'DualLiveCaptions.exe'))) {
    throw 'Run this script from the packaged DualLiveCaptions folder.'
}
$destinationFull = [IO.Path]::GetFullPath($Destination)
if ($destinationFull -eq [IO.Path]::GetFullPath($source)) { throw 'Choose a different installation folder.' }
New-Item -ItemType Directory -Force -Path $destinationFull | Out-Null
Get-ChildItem -LiteralPath $source | Copy-Item -Destination $destinationFull -Recurse -Force
$programs = [Environment]::GetFolderPath('Programs')
$wsh = New-Object -ComObject WScript.Shell
$link = $wsh.CreateShortcut((Join-Path $programs 'Dual Live Captions.lnk'))
$link.TargetPath = Join-Path $destinationFull 'DualLiveCaptions.exe'
$link.WorkingDirectory = $destinationFull
$link.IconLocation = $link.TargetPath
$link.Save()
Write-Output "Installed in $destinationFull. Open Dual Live Captions from Start."
