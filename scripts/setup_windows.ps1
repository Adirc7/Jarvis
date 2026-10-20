<#
Sets up Jarvis on Windows. Double-click "Setup Jarvis.cmd" to run it.

Safe to run again (after an update, or if a step failed): finished steps are
skipped or brought up to date.

Options, from PowerShell (e.g. .\scripts\setup_windows.ps1 -NoTamil):
  -NoTamil      skip the Tamil voice (saves about 1 GB: torch and transformers)
  -NoGpu        don't install the CUDA libraries, even with an NVIDIA GPU
  -SkipModels   don't download the voices and hand-tracking model
  -SkipTests    don't run the unit tests
  -NoShortcut   don't create the desktop and Start menu shortcuts
  -Quiet        ask nothing: keep Right Ctrl, skip Notepad and the hardware check

This file must stay plain ASCII: Windows PowerShell 5.1 misreads UTF-8 files
that have no byte-order mark.
#>
[CmdletBinding()]
param(
    [switch]$NoTamil,
    [switch]$NoGpu,
    [switch]$SkipModels,
    [switch]$SkipTests,
    [switch]$NoShortcut,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
$env:PYTHONUTF8 = "1"       # Sinhala and Tamil text through pipes and files
$OnWindows = $env:OS -eq "Windows_NT"
$FirstRun = -not (Test-Path -LiteralPath (Join-Path $Root ".venv"))
$Warnings = New-Object System.Collections.Generic.List[string]
$script:StepNumber = 0
$TotalSteps = 8

function Write-Step([string]$Text) {
    $script:StepNumber++
    Write-Host ""
    Write-Host "[$($script:StepNumber)/$TotalSteps] $Text" -ForegroundColor Cyan
}
function Write-Ok([string]$Text) { Write-Host "  OK  $Text" -ForegroundColor Green }
function Write-Note([string]$Text) { Write-Host "      $Text" }
function Add-Warning([string]$Text) {
    $script:Warnings.Add($Text)
    Write-Host "  !!  $Text" -ForegroundColor Yellow
}
function Read-YesNo([string]$Question, [bool]$Default) {
    if ($Quiet) { return $Default }
    $hint = if ($Default) { "[Y/n]" } else { "[y/N]" }
    $answer = Read-Host "      $Question $hint"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
    return $answer.Trim().ToLower().StartsWith("y")
}

# Output of a native command, or $null if it fails. Windows PowerShell 5.1
# turns redirected stderr into errors, so errors are relaxed in here.
function Get-NativeOutput([string]$Exe, [string[]]$Arguments) {
    $ErrorActionPreference = "Continue"
    try {
        $out = & $Exe @Arguments 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        return $out
    } catch {
        return $null
    }
}

function Find-Uv {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $dirs = @()
    if ($env:XDG_BIN_HOME) { $dirs += $env:XDG_BIN_HOME }
    if ($env:USERPROFILE) {
        $dirs += Join-Path $env:USERPROFILE ".local\bin"
        $dirs += Join-Path $env:USERPROFILE ".cargo\bin"
    }
    foreach ($dir in $dirs) {
        $exe = Join-Path $dir "uv.exe"
        if (Test-Path -LiteralPath $exe -PathType Leaf) {
            $env:Path = "$dir;$env:Path"      # for this window; the installer saved it for new ones
            return $exe
        }
    }
    return $null
}

# What a line of Python prints inside Jarvis's environment, or $Default.
# Keep double quotes out of $Code: Windows PowerShell 5.1 mangles them.
function Get-PythonOutput([string]$Code, [string]$Default) {
    $out = Get-NativeOutput $Uv @("run", "--no-sync", "python", "-c", $Code)
    if ($out) { return ([string]($out | Select-Object -Last 1)).Trim() }
    return $Default
}

function Get-ConfiguredKeys([string]$Path) {
    $found = @()
    if (-not (Test-Path -LiteralPath $Path)) { return $found }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match '^\s*([A-Z0-9_]+_API_KEY)\s*=\s*["'']?([^"''\s#]+)') { $found += $Matches[1] }
    }
    return $found
}

function New-Shortcut([string]$Path, [string]$Target, [string]$Arguments, [string]$Icon, [string]$Description) {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($Path)
    $link.TargetPath = $Target
    $link.Arguments = $Arguments
    $link.WorkingDirectory = $Root
    $link.Description = $Description
    if (Test-Path -LiteralPath $Icon) { $link.IconLocation = "$Icon,0" }
    $link.Save()
}

# Where the big downloads go when Jarvis lives on another drive than Windows:
# a .cache folder next to the project folder (D:\Projects\.cache for
# D:\Projects\Jarvis), so they don't fill up C:. The uv cache must be on the
# same drive as the project, or uv copies every package twice.
function Get-CacheVariables([string]$ProjectRoot) {
    $cacheRoot = Join-Path (Split-Path -Parent $ProjectRoot) ".cache"
    $vars = [ordered]@{}
    $vars["UV_CACHE_DIR"] = Join-Path $cacheRoot "uv"                    # downloaded packages
    $vars["UV_PYTHON_INSTALL_DIR"] = Join-Path $cacheRoot "uv-python"    # Python 3.12 itself
    $vars["HF_HOME"] = Join-Path $cacheRoot "huggingface"                # Whisper and MMS models
    $vars["OLLAMA_MODELS"] = Join-Path $cacheRoot "ollama-models"        # Ollama models
    return $vars
}

function Set-UserVariable([string]$Name, [string]$Value) {
    [Environment]::SetEnvironmentVariable($Name, $Value, "User")   # for every new window
    Set-Item -Path "Env:$Name" -Value $Value                          # for this one
}

function Test-VcRuntime {
    $sys = Join-Path $env:WINDIR "System32"
    return (Test-Path (Join-Path $sys "msvcp140.dll")) -and (Test-Path (Join-Path $sys "vcruntime140_1.dll"))
}

function Install-VcRuntime {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        & winget install --id Microsoft.VCRedist.2015+.x64 -e --accept-source-agreements --accept-package-agreements
    } else {
        $exe = Join-Path $env:TEMP "vc_redist.x64.exe"
        Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vc_redist.x64.exe" -OutFile $exe -UseBasicParsing
        Start-Process -FilePath $exe -ArgumentList "/install", "/passive", "/norestart" -Wait
    }
}

try {
    Write-Host "Jarvis setup" -ForegroundColor Cyan
    Write-Host "Folder: $Root"
    if ($FirstRun) {
        Write-Host "First run: this downloads a few GB, so it can take a while."
    }

    if ($Root -match "OneDrive") {
        Write-Host ""
        Write-Host "  !!  This folder is inside OneDrive. OneDrive would try to upload the" -ForegroundColor Yellow
        Write-Host "      packages (thousands of files, a few GB) and can lock them mid-install." -ForegroundColor Yellow
        Write-Host "      Better: move the Jarvis folder to e.g. C:\Users\<you>\Jarvis and run setup there." -ForegroundColor Yellow
        if (-not (Read-YesNo "Continue here anyway?" $false)) { exit 1 }
    }

    if ($OnWindows) {
        # Files from a downloaded ZIP carry a "came from the internet" mark that
        # makes Windows warn every time the launchers run.
        @($Root, (Join-Path $Root "scripts")) |
            ForEach-Object { Get-ChildItem -LiteralPath $_ -File } |
            Where-Object { $_.Extension -in ".cmd", ".ps1" } |
            Unblock-File -ErrorAction SilentlyContinue
    }

    # 1 ---------------------------------------------------------------------
    Write-Step "Disk space and tools"
    $drive = [IO.Path]::GetPathRoot($Root)
    try {
        $freeGb = [math]::Round((New-Object System.IO.DriveInfo($drive)).AvailableFreeSpace / 1GB, 1)
        if ($freeGb -lt 10) {
            Add-Warning "Only $freeGb GB free on $drive. Jarvis needs roughly 6 GB, plus 2.5 GB with Ollama."
        } else {
            Write-Ok "$freeGb GB free on $drive"
        }
    } catch { }

    if ($OnWindows -and $drive -and ($drive.TrimEnd('\') -ne $env:SystemDrive)) {
        $cacheVars = Get-CacheVariables $Root
        $unset = @($cacheVars.Keys | Where-Object { -not [Environment]::GetEnvironmentVariable($_) })
        if ($unset.Count -eq 0) {
            Write-Ok "downloads already kept off $($env:SystemDrive) ($($cacheVars['UV_CACHE_DIR']) and others)"
        } else {
            Write-Note "Jarvis is on $($drive.TrimEnd('\')) but the package cache, Python and Whisper/Ollama models"
            Write-Note "would still download to $($env:SystemDrive) (several GB)."
            $cacheRoot = Split-Path -Parent $cacheVars["UV_CACHE_DIR"]
            if (Read-YesNo "Keep them on $($drive.TrimEnd('\')) as well, in ${cacheRoot}?" $true) {
                foreach ($name in $unset) { Set-UserVariable $name $cacheVars[$name] }
                Write-Ok ("set for your user account: " + ($unset -join ", "))
                if (Get-Process ollama -ErrorAction SilentlyContinue) {
                    Write-Note "Quit and reopen Ollama so it uses the new models folder."
                }
            } else {
                Write-Note "Keeping the default locations on $($env:SystemDrive)."
            }
        }
    }

    $Uv = Find-Uv
    if ($Uv) {
        Write-Ok "uv found: $Uv"
    } else {
        Write-Note "Installing uv from astral.sh ..."
        $ps = (Get-Process -Id $PID).Path
        & $ps -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072; irm https://astral.sh/uv/install.ps1 | iex"
        $Uv = Find-Uv
        if (-not $Uv) { throw "uv didn't install. Install it by hand (https://docs.astral.sh/uv/) and run setup again." }
        Write-Ok "uv installed: $Uv"
    }
    $uvVersion = Get-NativeOutput $Uv @("--version")
    if ($uvVersion) { Write-Note $uvVersion }

    if ($OnWindows) {
        if (Test-VcRuntime) {
            Write-Ok "Microsoft Visual C++ runtime found"
        } else {
            Write-Note "The speech and vision libraries need the Microsoft Visual C++ runtime."
            if (Read-YesNo "Install it now? (Windows will ask for permission)" $true) {
                Install-VcRuntime
                if (Test-VcRuntime) { Write-Ok "Visual C++ runtime installed" }
                else { Add-Warning "Visual C++ runtime still missing. Get it from https://aka.ms/vs/17/release/vc_redist.x64.exe" }
            } else {
                Add-Warning "Without the Visual C++ runtime, Whisper and the voices may fail to load."
            }
        }
    }

    # 2 ---------------------------------------------------------------------
    Write-Step "Python 3.12 and packages"
    $extras = @("voice", "vision", "desktop", "dev")
    $gpu = $null
    if ($OnWindows -and -not $NoGpu) {
        $gpu = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "NVIDIA" } | Select-Object -First 1
    }
    if ($gpu) {
        $extras += "gpu"
        Write-Note "NVIDIA GPU: $($gpu.Name). Installing the CUDA libraries so Whisper runs on it."
        $driver = Get-NativeOutput "nvidia-smi" @("--query-gpu=driver_version", "--format=csv,noheader")
        if ($driver) {
            $driver = ([string]($driver | Select-Object -First 1)).Trim()
            Write-Note "Driver $driver"
            try {
                if ([double]$driver -lt 528) {
                    Add-Warning "NVIDIA driver $driver is older than Whisper's CUDA 12 needs (528 or newer). Update it from nvidia.com or the NVIDIA app."
                }
            } catch { }
        }
    } elseif ($NoGpu) {
        Write-Note "Skipping the CUDA libraries (-NoGpu). Whisper will run on the CPU."
    } else {
        Write-Note "No NVIDIA GPU found. Whisper will run on the CPU (slower)."
    }
    if ($NoTamil) { Write-Note "Skipping the Tamil voice (-NoTamil)." } else { $extras += "mms" }
    $syncArgs = @("sync")
    foreach ($extra in $extras) { $syncArgs += "--extra"; $syncArgs += $extra }
    Write-Note ("uv " + ($syncArgs -join " "))
    & $Uv @syncArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Installing the packages failed (see the messages above). Check the internet connection and run setup again."
    }
    Write-Ok "packages installed"

    # 3 ---------------------------------------------------------------------
    Write-Step "Voices and hand-tracking model"
    if ($SkipModels) {
        Write-Note "skipped (-SkipModels)"
    } else {
        & $Uv run --no-sync python scripts/download_models.py
        if ($LASTEXITCODE -ne 0) {
            Add-Warning "Some model downloads failed. Run setup again to retry; finished files are kept."
        } else {
            Write-Ok "models ready"
        }
    }

    # 4 ---------------------------------------------------------------------
    Write-Step "Free LLM access (.env)"
    $envFile = Join-Path $Root ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        Copy-Item -LiteralPath (Join-Path $Root ".env.example") -Destination $envFile
        Write-Note "Created .env from .env.example"
    }
    $keys = @(Get-ConfiguredKeys $envFile)
    if ($keys.Count -eq 0 -and $OnWindows -and -not $Quiet) {
        Write-Note "Jarvis needs at least one free key to answer (or Ollama, below). Easiest:"
        Write-Note "  Gemini  https://aistudio.google.com/apikey"
        Write-Note "  Groq    https://console.groq.com/keys"
        if (Read-YesNo "Open both pages in your browser?" $true) {
            Start-Process "https://aistudio.google.com/apikey"
            Start-Process "https://console.groq.com/keys"
        }
        Write-Note "Notepad opens .env now. Paste each key right after its = sign, then save."
        # No -Wait: Windows 11 Notepad may open the file in an existing window
        # and return at once, so ask instead.
        Start-Process -FilePath "notepad.exe" -ArgumentList ('"' + $envFile + '"')
        Read-Host "      Press Enter here once you've saved .env" | Out-Null
        $keys = @(Get-ConfiguredKeys $envFile)
    }
    if ($keys.Count -gt 0) {
        Write-Ok ("keys in .env: " + ($keys -join ", "))
    } else {
        Add-Warning "No LLM key in .env yet. Add one (notepad .env) or set up Ollama, or Jarvis can't answer."
    }
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        $model = Get-PythonOutput "from jarvis.config import load_settings; print(load_settings().get('llm.providers.ollama.model', 'qwen3:4b'))" "qwen3:4b"
        $list = Get-NativeOutput "ollama" @("list")
        if ($list -and ($list -match [regex]::Escape($model))) {
            Write-Ok "Ollama has $model, so Jarvis also works offline"
        } elseif (Read-YesNo "Ollama is installed. Download $model for offline answers (about 2.5 GB)?" $false) {
            & ollama pull $model
            if ($LASTEXITCODE -ne 0) { Add-Warning "ollama pull $model failed." }
        }
    } else {
        Write-Note "Optional: Ollama (https://ollama.com) lets Jarvis answer without internet."
    }

    # 5 ---------------------------------------------------------------------
    Write-Step "Push-to-talk key"
    $localFile = Join-Path (Join-Path $Root "config") "settings.local.toml"
    $chosen = (Test-Path -LiteralPath $localFile) -and
        [bool](Select-String -LiteralPath $localFile -Pattern '^\s*push_to_talk\s*=' -Quiet)
    if ($chosen) {
        Write-Ok "already chosen (config\settings.local.toml)"
    } elseif ($Quiet -or -not $OnWindows) {
        Write-Note "Using Right Ctrl. To change it later: uv run python scripts/choose_key.py"
    } else {
        Write-Note "You hold one key while talking to Jarvis; the default is Right Ctrl."
        Write-Note "Many new laptops have a Copilot key where Right Ctrl used to be; that one won't work."
        if (Read-YesNo "Is there a key labelled Ctrl to the right of the space bar (not Copilot)?" $true) {
            & $Uv run --no-sync python scripts/choose_key.py --name ctrl_r
        } else {
            & $Uv run --no-sync python scripts/choose_key.py
        }
        if ($LASTEXITCODE -ne 0) { Add-Warning "Push-to-talk key not saved. Later: uv run python scripts/choose_key.py" }
    }

    # 6 ---------------------------------------------------------------------
    Write-Step "Unit tests (no microphone or camera needed)"
    if ($SkipTests) {
        Write-Note "skipped (-SkipTests)"
    } else {
        & $Uv run --no-sync pytest -q -p no:cacheprovider
        if ($LASTEXITCODE -ne 0) { Add-Warning "Some unit tests failed; the output above says which." }
        else { Write-Ok "all tests passed" }
    }

    # 7 ---------------------------------------------------------------------
    Write-Step "Shortcuts"
    if ($NoShortcut -or -not $OnWindows) {
        Write-Note "skipped"
    } else {
        $runner = Join-Path $Root "scripts\run_jarvis.cmd"
        $icon = Join-Path $Root "assets\jarvis.ico"
        $desktop = [Environment]::GetFolderPath("Desktop")
        $programs = [Environment]::GetFolderPath("Programs")
        New-Shortcut (Join-Path $desktop "Jarvis.lnk") $runner "voice" $icon "Talk to Jarvis"
        New-Shortcut (Join-Path $programs "Jarvis.lnk") $runner "voice" $icon "Talk to Jarvis"
        New-Shortcut (Join-Path $programs "Jarvis (text chat).lnk") $runner "text" $icon "Chat with Jarvis by typing"
        Write-Ok "Jarvis on the desktop; Jarvis and Jarvis (text chat) in the Start menu"
    }

    # 8 ---------------------------------------------------------------------
    Write-Step "Hardware check: microphone, speakers, camera, GPU, voices"
    Write-Note "Records 6 s from the mic, plays each voice, and downloads Whisper (about 500 MB) the first time."
    if ((-not $Quiet) -and (Read-YesNo "Run it now?" $FirstRun)) {
        & $Uv run --no-sync python scripts/smoke_test.py
        if ($LASTEXITCODE -ne 0) { Add-Warning "The hardware check found problems; the table above shows which." }
        else { Write-Ok "hardware check passed" }
    } else {
        Write-Note "Later: uv run python scripts/smoke_test.py --show"
    }

    # Summary ---------------------------------------------------------------
    $pttLabel = Get-PythonOutput "from jarvis.config import load_settings; from jarvis.voice.capture import describe_key; print(describe_key(load_settings().get('hotkeys.push_to_talk', 'ctrl_r')))" "Right Ctrl"
    Write-Host ""
    if ($Warnings.Count -eq 0) {
        Write-Host "Jarvis is set up." -ForegroundColor Green
    } else {
        Write-Host "Jarvis is set up, with $($Warnings.Count) thing(s) to look at:" -ForegroundColor Yellow
        foreach ($w in $Warnings) { Write-Host "  - $w" -ForegroundColor Yellow }
    }
    Write-Host ""
    Write-Host "Start:  double-click Jarvis on the desktop (or Start Jarvis.cmd in this folder)."
    Write-Host "Talk:   hold $pttLabel, speak, let go. Press it while Jarvis speaks to interrupt."
    Write-Host "Keys:   Ctrl+Alt+M mutes replies, Ctrl+Alt+K stops everything."
    Write-Host "Update: git pull, then run Setup Jarvis.cmd again."
    exit 0
} catch {
    Write-Host ""
    Write-Host "Setup stopped: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Fix that and run Setup Jarvis.cmd again; finished steps are skipped." -ForegroundColor Red
    exit 1
}
