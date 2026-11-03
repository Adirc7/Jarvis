<#
Clap three times to open Jarvis (src/jarvis/clap_launcher.py).

  scripts\clap_launcher.cmd install     start it now, and every time you sign in to Windows
  scripts\clap_launcher.cmd uninstall   stop it, and don't start it at sign-in any more
  scripts\clap_launcher.cmd test        run it in this window, printing each clap it hears

It listens for claps only: each 10 ms of sound is measured and dropped, nothing is recorded.
This file must stay plain ASCII: Windows PowerShell 5.1 misreads UTF-8 files without a BOM.
#>
param([string]$Action = "install")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $Root ".venv\Scripts\pythonw.exe"
$python = Join-Path $Root ".venv\Scripts\python.exe"
$startup = [Environment]::GetFolderPath("Startup")
$link = Join-Path $startup "Jarvis clap launcher.lnk"
$icon = Join-Path $Root "assets\jarvis.ico"

function Stop-Launcher {
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*jarvis.clap_launcher*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

if ($Action -eq "install") {
    if (-not (Test-Path -LiteralPath $pythonw)) { throw "Jarvis isn't set up here yet: $pythonw is missing (run scripts\setup.cmd)." }
    $shell = New-Object -ComObject WScript.Shell
    $l = $shell.CreateShortcut($link)
    $l.TargetPath = $pythonw
    $l.Arguments = "-m jarvis.clap_launcher"
    $l.WorkingDirectory = $Root
    $l.Description = "Clap three times to open Jarvis"
    if (Test-Path -LiteralPath $icon) { $l.IconLocation = "$icon,0" }
    $l.Save()
    Stop-Launcher
    Start-Process -FilePath $pythonw -ArgumentList "-m", "jarvis.clap_launcher" -WorkingDirectory $Root
    Write-Host "  OK  Listening for three claps now, and from every sign-in. Clap three times to try it." -ForegroundColor Green
    Write-Host "      Its log: logs\clap_launcher.log. To stop: scripts\clap_launcher.cmd uninstall"
} elseif ($Action -eq "uninstall") {
    if (Test-Path -LiteralPath $link) { Remove-Item -LiteralPath $link }
    Stop-Launcher
    Write-Host "  OK  Stopped; it won't start at sign-in any more." -ForegroundColor Green
} elseif ($Action -eq "stop") {
    Stop-Launcher                                   # update.cmd: Python's files must be free to replace
} elseif ($Action -eq "resume") {
    if (Test-Path -LiteralPath $link) {             # only if it was installed
        Start-Process -FilePath $pythonw -ArgumentList "-m", "jarvis.clap_launcher" -WorkingDirectory $Root
        Write-Host "  OK  Clap launcher listening again" -ForegroundColor Green
    }
} elseif ($Action -eq "test") {
    Stop-Launcher
    Write-Host "Clap three times (Ctrl+C to stop). Each clap it hears is printed."
    & $python -m jarvis.clap_launcher --console
} else {
    throw "Use install, uninstall or test."
}
