param(
    [string]$Version = $env:TOPO_VERSION,
    [string]$InstallDir = $env:TOPO_INSTALL_DIR
)

$ErrorActionPreference = "Stop"
$Repo = "arjenvanputten/topo"
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

$Archive = "topo-windows-amd64.zip"
$Url = "https://github.com/$Repo/releases/download/$Version/$Archive"
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) "topo-install-$PID"
$ZipPath = Join-Path $TempDir $Archive

try {
    Write-Host "Installing Topo $Version for windows-amd64..."
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
    Invoke-WebRequest -Uri $Url -OutFile $ZipPath
    Expand-Archive -Path $ZipPath -DestinationPath $TempDir -Force

    $DownloadedBinary = Join-Path $TempDir "topo.exe"
    if (-not (Test-Path $DownloadedBinary -PathType Leaf)) {
        throw "Release archive has no topo.exe binary"
    }

    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    $TemporaryTarget = Join-Path $InstallDir ".topo.new.exe"
    Copy-Item $DownloadedBinary $TemporaryTarget -Force
    Move-Item $TemporaryTarget (Join-Path $InstallDir "topo.exe") -Force

    & (Join-Path $InstallDir "topo.exe") --version

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
    Write-Host "Topo is installed at $(Join-Path $InstallDir 'topo.exe')"
} finally {
    if (Test-Path $TempDir) {
        Remove-Item -Recurse -Force $TempDir
    }
}
