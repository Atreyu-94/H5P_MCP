param([Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = Join-Path $repo '.venv/Scripts/python.exe'
if (-not $IsWindows) { $python = Join-Path $repo '.venv/bin/python' }
$stage = Join-Path ([IO.Path]::GetTempPath()) ('h5p-browser-baseline-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
$core = Join-Path $stage 'core'
$revision = '2aeb0b83fa603e331381b3a6b8bf42c3773ba140'
$npm = if ($IsWindows) { 'npm.cmd' } else { 'npm' }
& $npm ci --prefix $PSScriptRoot --ignore-scripts --no-audit --no-fund
if ($LASTEXITCODE) { throw 'Tooling installation failed' }
& git init --quiet $core
if ($LASTEXITCODE) { throw 'Core init failed' }
& git -C $core fetch --quiet --depth=1 https://github.com/h5p/h5p-php-library.git $revision
if ($LASTEXITCODE) { throw 'Core fetch failed' }
& git -C $core checkout --quiet --detach FETCH_HEAD
if ($LASTEXITCODE) { throw 'Core checkout failed' }
$actual = & git -C $core rev-parse HEAD
if ($actual -ne $revision) { throw 'Core revision mismatch' }
$fixtureLog = @(& $python (Join-Path $PSScriptRoot 'browser-fixture.py') $stage)
if ($LASTEXITCODE) { throw 'Fixture generation failed' }
$fixture = $fixtureLog[-1] | ConvertFrom-Json
$previous = $env:H5P_MCP_GRADING_SMOKE
try {
    $env:H5P_MCP_GRADING_SMOKE = '1'
    $log = @(& node (Join-Path $repo 'tests/lumi_browser_smoke.cjs') $fixture.runtime $PSScriptRoot $core $fixture.packages)
    if ($LASTEXITCODE) { throw 'Browser smoke failed' }
    $report = [ordered]@{
        status = 'passed'
        head = (& git -c "safe.directory=$($repo.Replace('\','/'))" -C $repo rev-parse HEAD)
        core = $revision
        node = (& node --version)
        os = [Runtime.InteropServices.RuntimeInformation]::OSDescription
        fixtureLog = $fixtureLog
        results = @($log | ForEach-Object { $_ | ConvertFrom-Json })
        artifactDirectory = $stage
    }
    $report | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $OutputPath -Encoding utf8NoBOM
} finally {
    if ($null -eq $previous) { Remove-Item Env:H5P_MCP_GRADING_SMOKE -ErrorAction SilentlyContinue }
    else { $env:H5P_MCP_GRADING_SMOKE = $previous }
}
# Keep our unique directory for diagnosis; never remove another run's artifacts.
