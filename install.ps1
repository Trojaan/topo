param(
    [string]$Version = $env:TOPO_VERSION,
    [string]$InstallDir = $env:TOPO_INSTALL_DIR
)

$ErrorActionPreference = "Stop"
$Repo = "Trojaan/topo"
if (-not $InstallDir) {
    $InstallDir = Join-Path $env:LOCALAPPDATA "topo\bin"
}

if (-not $Version) {
    try {
        $Version = (Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest").tag_name
    } catch {
        Write-Error "Could not determine the latest Topo release: $_"
        exit 1
    }
}

$ReleaseVersion = [version]($Version -replace '^v', '')
$Commands = @("topo")
if ($ReleaseVersion -ge [version]"0.6.0") {
    $Commands += "topo2"
}
$ExpectedVersion = $Version -replace '^v', ''
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.IO.Path]::GetRandomFileName())

try {
    Write-Host "Installing Topo $Version for windows-amd64..."
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
    # Validate every download before replacing any existing command.
    foreach ($Command in $Commands) {
        $Archive = "$Command-windows-amd64.zip"
        $Url = "https://github.com/$Repo/releases/download/$Version/$Archive"
        $ZipPath = Join-Path $TempDir $Archive
        $ExtractDir = Join-Path $TempDir $Command
        Invoke-WebRequest -Uri $Url -OutFile $ZipPath
        Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force
        $DownloadedBinary = Join-Path $ExtractDir "$Command.exe"
        if (-not (Test-Path $DownloadedBinary -PathType Leaf)) {
            throw "Release archive has no $Command.exe binary"
        }
        $ActualVersion = & $DownloadedBinary --version
        if ($LASTEXITCODE -ne 0 -or $ActualVersion -ne "$Command $ExpectedVersion") {
            throw "$Command reports a different version or cannot run"
        }
    }

    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    foreach ($Command in $Commands) {
        $DownloadedBinary = Join-Path (Join-Path $TempDir $Command) "$Command.exe"
        $TemporaryTarget = Join-Path $InstallDir ".$Command.new.exe"
        Copy-Item $DownloadedBinary $TemporaryTarget -Force
        Move-Item $TemporaryTarget (Join-Path $InstallDir "$Command.exe") -Force
        & (Join-Path $InstallDir "$Command.exe") --version
        if ($LASTEXITCODE -ne 0) {
            throw "Installed $Command cannot run"
        }
    }

    if ($env:GITHUB_ACTIONS) {
        $InstallDir | Out-File -FilePath $env:GITHUB_PATH -Append -Encoding utf8
    } else {
        $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $Entries = @($UserPath -split ";" | Where-Object { $_ })
        if ($Entries -notcontains $InstallDir) {
            $NewPath = (@($Entries) + $InstallDir) -join ";"
            [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
            Write-Host "Added Topo to the user PATH; restart your terminal."
        }
    }
    foreach ($Command in $Commands) {
        Write-Host "$Command is installed at $(Join-Path $InstallDir "$Command.exe")"
    }
} finally {
    if (Test-Path $TempDir) {
        Remove-Item -Recurse -Force $TempDir
    }
}
