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
$RuntimeStage = $null

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
    $InstallDir = (Resolve-Path -LiteralPath $InstallDir).Path
    foreach ($Command in $Commands) {
        $ExtractDir = Join-Path $TempDir $Command
        if ($Command -eq "topo2") {
            foreach ($Runtime in Get-ChildItem -Path $ExtractDir -Directory -Filter "_topo2_runtime_*") {
                $RuntimeTarget = Join-Path $InstallDir $Runtime.Name
                if (Test-Path $RuntimeTarget) {
                    # Never overwrite files used by a running or previous executable.
                    $Incoming = @(Get-ChildItem $Runtime.FullName -Recurse -File | ForEach-Object {
                        $_.FullName.Substring($Runtime.FullName.Length) + ":" + (Get-FileHash $_.FullName).Hash
                    })
                    $Existing = @(Get-ChildItem $RuntimeTarget -Recurse -File | ForEach-Object {
                        $_.FullName.Substring($RuntimeTarget.Length) + ":" + (Get-FileHash $_.FullName).Hash
                    })
                    if (@(Compare-Object $Incoming $Existing).Count -ne 0) {
                        throw "Installed runtime differs; existing installation preserved"
                    }
                } else {
                    $RuntimeStage = Join-Path $InstallDir (".topo2-runtime-" + [guid]::NewGuid())
                    Copy-Item $Runtime.FullName $RuntimeStage -Recurse
                    Move-Item $RuntimeStage $RuntimeTarget
                    $RuntimeStage = $null
                }
            }
        }
        $DownloadedBinary = Join-Path $ExtractDir "$Command.exe"
        $TemporaryTarget = Join-Path $InstallDir ".$Command.new.exe"
        Copy-Item $DownloadedBinary $TemporaryTarget -Force
        $ActualVersion = & $TemporaryTarget --version
        if ($LASTEXITCODE -ne 0 -or $ActualVersion -ne "$Command $ExpectedVersion") {
            throw "Staged $Command cannot run or reports a different version"
        }
        if ($Command -eq "topo2") {
            & $TemporaryTarget contract show | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Staged topo2 runtime cannot load" }
        }
    }
    foreach ($Command in $Commands) {
        Move-Item (Join-Path $InstallDir ".$Command.new.exe") (Join-Path $InstallDir "$Command.exe") -Force
        & (Join-Path $InstallDir "$Command.exe") --version
        if ($LASTEXITCODE -ne 0) { throw "Installed $Command cannot run" }
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
    foreach ($Command in $Commands) {
        $StagedBinary = Join-Path $InstallDir ".$Command.new.exe"
        if (Test-Path $StagedBinary) { Remove-Item $StagedBinary -Force }
    }
    if ($RuntimeStage -and (Test-Path $RuntimeStage)) { Remove-Item $RuntimeStage -Recurse -Force }
    if (Test-Path $TempDir) {
        Remove-Item -Recurse -Force $TempDir
    }
}
