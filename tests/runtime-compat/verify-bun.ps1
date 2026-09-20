param([Parameter(Mandatory)][string]$BunPath, [Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
$architecture = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
$platform = if ($IsWindows -and $architecture -eq 'X64') { 'windows-x64' }
            elseif ($IsLinux -and $architecture -eq 'X64') { 'linux-x64' }
            elseif ($IsMacOS -and $architecture -eq 'Arm64') { 'darwin-aarch64' }
            else { throw 'Platform outside the initial Bun matrix' }
# Official GitHub bun-v1.4.2 release asset digests, verified 2026-09-19.
$hashes = @{
    'windows-x64'='ce4c17497b2f29712a99d3d53f028de28cd42e3bacb8589599e7f000e49b6405'
    'linux-x64'='36368faef7527875d5ffa52e53cd48021741f2a83eb6208a8dd64068d422a913'
    'darwin-aarch64'='90987a3a16d7db556d886ac3d551e7b6d3edf0a1cf43acaed622e8676be1d12f'
}
$stage = Join-Path ([IO.Path]::GetTempPath()) ('h5p-bun-verify-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
$archive = Join-Path $stage 'bun.zip'
Invoke-WebRequest "https://github.com/oven-sh/bun/releases/download/bun-v1.4.2/bun-$platform.zip" -OutFile $archive
$actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $hashes[$platform]) { throw 'Bun archive checksum mismatch' }
Expand-Archive -LiteralPath $archive -DestinationPath $stage
$binary = if ($IsWindows) { 'bun.exe' } else { 'bun' }
$expectedBinary = (Get-FileHash -LiteralPath (Join-Path $stage "bun-$platform/$binary") -Algorithm SHA256).Hash
$installedBinary = (Get-FileHash -LiteralPath $BunPath -Algorithm SHA256).Hash
if ($expectedBinary -ne $installedBinary) { throw 'Installed Bun differs from the pinned official binary' }
$version = & $BunPath --version
if ($LASTEXITCODE -or $version -ne '1.4.2') { throw 'Unexpected Bun runtime version' }
@{status='passed';platform=$platform;version=$version;archiveSha256=$actual;binarySha256=$installedBinary.ToLowerInvariant()} |
    ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding utf8NoBOM
