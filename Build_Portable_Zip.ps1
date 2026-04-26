$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ProjectRoot = $PSScriptRoot
$DistDir = Join-Path $ProjectRoot 'dist'
$StageRoot = Join-Path $DistDir '_portable_stage'
$PackageRoot = Join-Path $StageRoot 'AI-image2-portable'
$ZipPath = Join-Path $DistDir 'AI-image2-portable.zip'
$RuntimeExe = Join-Path $ProjectRoot 'runtime\AI_Image2_Server.exe'

$ExcludedDirectoryNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@('cache', '.venv', '__pycache__', '.git', 'dist') | ForEach-Object {
    [void]$ExcludedDirectoryNames.Add($_)
}

$ExcludedFileNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@('local_config.json') | ForEach-Object {
    [void]$ExcludedFileNames.Add($_)
}

$ExcludedExtensions = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@('.log') | ForEach-Object {
    [void]$ExcludedExtensions.Add($_)
}

function Write-Step {
    param([string]$Message)
    Write-Host "[Build Portable Zip] $Message"
}

function Get-RelativePathCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,
        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    $baseResolved = (Resolve-Path -LiteralPath $BasePath).ProviderPath.TrimEnd('\') + '\'
    $targetResolved = (Resolve-Path -LiteralPath $TargetPath).ProviderPath
    $baseUri = [System.Uri]::new($baseResolved)
    $targetUri = [System.Uri]::new($targetResolved)
    return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($targetUri).ToString()).Replace('/', '\')
}

function Test-ShouldExclude {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,
        [Parameter(Mandatory = $true)]
        [bool]$IsDirectory
    )

    $segments = $RelativePath -split '[\\/]'
    foreach ($segment in $segments) {
        if ($ExcludedDirectoryNames.Contains($segment)) {
            return $true
        }
    }

    if (-not $IsDirectory) {
        $leafName = [System.IO.Path]::GetFileName($RelativePath)
        if ($ExcludedFileNames.Contains($leafName)) {
            return $true
        }

        $extension = [System.IO.Path]::GetExtension($leafName)
        if ($ExcludedExtensions.Contains($extension)) {
            return $true
        }
    }

    return $false
}

function Copy-FilteredTree {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceDir,
        [Parameter(Mandatory = $true)]
        [string]$DestinationDir
    )

    foreach ($item in Get-ChildItem -Force -LiteralPath $SourceDir) {
        $relativePath = Get-RelativePathCompat -BasePath $ProjectRoot -TargetPath $item.FullName
        if (Test-ShouldExclude -RelativePath $relativePath -IsDirectory $item.PSIsContainer) {
            continue
        }

        $targetPath = Join-Path $DestinationDir $item.Name
        if ($item.PSIsContainer) {
            New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
            Copy-FilteredTree -SourceDir $item.FullName -DestinationDir $targetPath
            continue
        }

        Copy-Item -LiteralPath $item.FullName -Destination $targetPath -Force
    }
}

try {
    Write-Step ("Project root: {0}" -f $ProjectRoot)

    if (-not (Test-Path -LiteralPath $RuntimeExe -PathType Leaf)) {
        throw ("Bundled runtime is missing: {0}" -f $RuntimeExe)
    }

    if (Test-Path -LiteralPath $StageRoot) {
        Remove-Item -LiteralPath $StageRoot -Recurse -Force
    }

    New-Item -ItemType Directory -Path $DistDir -Force | Out-Null
    New-Item -ItemType Directory -Path $PackageRoot -Force | Out-Null

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }

    Write-Step 'Copying release files with exclusions: cache, *.log, local_config.json, .venv, __pycache__, .git, dist ...'
    Copy-FilteredTree -SourceDir $ProjectRoot -DestinationDir $PackageRoot

    $PackagedRuntimeExe = Join-Path $PackageRoot 'runtime\AI_Image2_Server.exe'
    if (-not (Test-Path -LiteralPath $PackagedRuntimeExe -PathType Leaf)) {
        throw 'Packaging validation failed: runtime\AI_Image2_Server.exe was not copied into the release tree.'
    }

    $unexpectedEntries = Get-ChildItem -LiteralPath $PackageRoot -Recurse -Force | Where-Object {
        $relativePath = Get-RelativePathCompat -BasePath $PackageRoot -TargetPath $_.FullName
        Test-ShouldExclude -RelativePath $relativePath -IsDirectory $_.PSIsContainer
    }
    if ($unexpectedEntries) {
        $paths = $unexpectedEntries | Select-Object -ExpandProperty FullName
        throw ("Packaging validation failed: excluded content was found in the release tree:`n- " + ($paths -join "`n- "))
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $PackageRoot,
        $ZipPath,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $true
    )

    $packagedFiles = Get-ChildItem -LiteralPath $PackageRoot -Recurse -File
    $totalBytes = ($packagedFiles | Measure-Object -Property Length -Sum).Sum
    $zipBytes = (Get-Item -LiteralPath $ZipPath).Length

    Write-Step ('Done: {0}' -f $ZipPath)
    Write-Step ('Runtime included: {0}' -f $PackagedRuntimeExe)
    Write-Step ('Packaged files: {0}' -f $packagedFiles.Count)
    Write-Step ('Uncompressed size: {0:N2} MB' -f ($totalBytes / 1MB))
    Write-Step ('Zip size: {0:N2} MB' -f ($zipBytes / 1MB))
}
catch {
    Write-Error $_
    exit 1
}
finally {
    if (Test-Path -LiteralPath $StageRoot) {
        Remove-Item -LiteralPath $StageRoot -Recurse -Force
    }
}
