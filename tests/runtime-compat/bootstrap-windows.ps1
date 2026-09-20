param([Parameter(Mandatory)][string]$Destination)
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -or [Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'X64') {
    throw 'This bootstrap is certified for download verification on Windows x64 only.'
}
$target = Join-Path $Destination ('bun-1.4.2-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $target | Out-Null
$archive = Join-Path $target 'bun.zip'
$expected = 'ce4c17497b2f29712a99d3d53f028de28cd42e3bacb8589599e7f000e49b6405'
Invoke-WebRequest 'https://github.com/oven-sh/bun/releases/download/bun-v1.4.2/bun-windows-x64.zip' -OutFile $archive
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw 'Official Bun archive SHA-256 mismatch; refusing execution'
}
Expand-Archive -LiteralPath $archive -DestinationPath $target
$executable = Join-Path $target 'bun-windows-x64/bun.exe'
$version = & $executable --version
if ($LASTEXITCODE -or $version -ne '1.4.2') { throw 'Unexpected Bun version' }
@{ executable=$executable; version=$version; archiveSha256=$expected } | ConvertTo-Json
