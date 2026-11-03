@echo off
rem Clap three times to open Jarvis: install, uninstall or test (see clap_launcher.ps1).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0clap_launcher.ps1" %*
