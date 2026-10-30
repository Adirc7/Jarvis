<#
Puts Jarvis on the desktop and in the Start menu. Setup and update run it;
safe to run any time (it replaces Jarvis's own shortcuts only).

  Jarvis                 Jarvis as an app: his window, the console minimized
  Jarvis (console)       the same, with the console in front (to watch what he hears)
  Jarvis (text chat)     typing in the console

This file must stay plain ASCII: Windows PowerShell 5.1 misreads UTF-8 files
that have no byte-order mark.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $Root "scripts\run_jarvis.cmd"
$icon = Join-Path $Root "assets\jarvis.ico"

function New-JarvisShortcut([string]$Path, [string]$Arguments, [string]$Description, [int]$Style) {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($Path)
    $link.TargetPath = $runner
    $link.Arguments = $Arguments
    $link.WorkingDirectory = $Root
    $link.Description = $Description
    $link.WindowStyle = $Style                   # 1 normal, 7 minimized
    if (Test-Path -LiteralPath $icon) { $link.IconLocation = "$icon,0" }
    $link.Save()
}

$desktop = [Environment]::GetFolderPath("Desktop")
$programs = [Environment]::GetFolderPath("Programs")
New-JarvisShortcut (Join-Path $desktop "Jarvis.lnk") "app" "Talk to Jarvis" 7
New-JarvisShortcut (Join-Path $programs "Jarvis.lnk") "app" "Talk to Jarvis" 7
New-JarvisShortcut (Join-Path $programs "Jarvis (console).lnk") "console" "Jarvis with his console in front" 1
New-JarvisShortcut (Join-Path $programs "Jarvis (text chat).lnk") "text" "Chat with Jarvis by typing" 1
Write-Host "  OK  Jarvis on the desktop; Jarvis, Jarvis (console) and Jarvis (text chat) in the Start menu" -ForegroundColor Green
