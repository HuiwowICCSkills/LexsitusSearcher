# Locate a Python that can run this skill, then hand off to
# scripts/lexsitus_search.py. requests and beautifulsoup4 are the only
# dependencies; no browser or Node.js is needed.
$lexCandidates = @(
    (Join-Path $PSScriptRoot 'venv\Scripts\python.exe'),
    (Join-Path $PSScriptRoot 'venv/bin/python'),
    (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    (Join-Path $env:USERPROFILE '.workbuddy\binaries\python\versions\3.13.12\python.exe')
)
$lexPathPython = (Get-Command python -ErrorAction SilentlyContinue).Source
if ($lexPathPython) { $lexCandidates += $lexPathPython }
$lexPathPython3 = (Get-Command python3 -ErrorAction SilentlyContinue).Source
if ($lexPathPython3) { $lexCandidates += $lexPathPython3 }

$lexPython = $null
foreach ($lexCandidate in $lexCandidates) {
    if (-not $lexCandidate -or -not (Test-Path -LiteralPath $lexCandidate -PathType Leaf)) { continue }
    & $lexCandidate -c 'import requests, bs4' 2>$null
    if ($LASTEXITCODE -eq 0) { $lexPython = $lexCandidate; break }
}
if (-not $lexPython) {
    throw 'No Python with requests and beautifulsoup4 was found. Run: python -m pip install -r requirements.txt (or create venv/).'
}
$lexArguments = foreach ($lexArgument in $args) {
    if ($lexArgument -is [array]) { $lexArgument -join ',' } else { $lexArgument }
}
& $lexPython -X utf8 (Join-Path $PSScriptRoot 'scripts\lexsitus_search.py') $lexArguments
exit $LASTEXITCODE
