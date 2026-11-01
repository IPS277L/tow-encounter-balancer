# Windows audit helper: fresh copy/build/venv, no changes to the working .venv.
param([Parameter(Mandatory)][string]$Repository, [Parameter(Mandatory)][string]$AuditDirectory)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $AuditDirectory) { throw 'Use a fresh audit directory' }
New-Item -ItemType Directory -Path $AuditDirectory | Out-Null
$package = Join-Path $AuditDirectory 'package'
New-Item -ItemType Directory -Path $package | Out-Null
foreach ($name in @('src', 'pyproject.toml', 'README.md', 'LICENSE')) {
    Copy-Item -LiteralPath (Join-Path $Repository $name) -Destination $package -Recurse
}
$python = Join-Path $Repository '.venv/Scripts/python.exe'
& $python -m pip wheel --no-deps --wheel-dir (Join-Path $AuditDirectory 'wheels') $package
if ($LASTEXITCODE -ne 0) { throw 'Wheel build failed' }
$installed = Join-Path $AuditDirectory 'installed'
& $python -m venv $installed
if ($LASTEXITCODE -ne 0) { throw 'Fresh venv creation failed' }
$site = Join-Path $installed 'Lib/site-packages'
$sourceSite = Join-Path $Repository '.venv/Lib/site-packages'
foreach ($name in @('attr', 'attrs', 'jsonschema', 'jsonschema_specifications', 'referencing', 'rpds', 'typing_extensions.py')) {
    Copy-Item -LiteralPath (Join-Path $sourceSite $name) -Destination $site -Recurse
}
foreach ($distribution in @('attrs', 'jsonschema', 'jsonschema_specifications', 'referencing', 'rpds_py', 'typing_extensions')) {
    $metadata = @(Get-ChildItem -LiteralPath $sourceSite -Directory | Where-Object { $_.Name -like "$distribution-*.dist-info" })
    if ($metadata.Count -ne 1) { throw "Expected one distribution: $distribution" }
    Copy-Item -LiteralPath $metadata[0].FullName -Destination $site -Recurse
}
$auditPython = Join-Path $installed 'Scripts/python.exe'
$wheel = Join-Path $AuditDirectory 'wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl'
& $auditPython -m pip install --no-index --no-deps $wheel
if ($LASTEXITCODE -ne 0) { throw 'Offline wheel installation failed' }
& $auditPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Installed dependency check failed' }
"Audit directory: $AuditDirectory"
