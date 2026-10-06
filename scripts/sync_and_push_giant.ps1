# Sync Giant Lewisburg weekly ad, solve BxGy prices, export to web/deals.json, and push to GitHub
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

Write-Host "=================================================="
Write-Host " Syncing Giant Lewisburg Weekly Ad & Solving BOGOs"
Write-Host "=================================================="

# 1. Run sync
& "app_automation\.venv\Scripts\python.exe" -m deals_tracker.src.cli sync --store giant

# 2. Export to web/deals.json
& "app_automation\.venv\Scripts\python.exe" -m deals_tracker.src.cli export --store giant --format json --output "deals_tracker/web/deals.json"

# 3. Git commit and push web/deals.json
Set-Location "$RepoRoot\deals_tracker"
git add "web/deals.json" "src/giant_grid_fetcher.py" "src/cli.py"

$staged = git diff --staged --name-only
if ($staged) {
    Write-Host "Changes detected in web/deals.json. Pushing to GitHub (main & gh-pages)..."
    git commit -m "chore(web): update weekly Giant deals with solved BxGy prices"
    git push origin main
    
    $tree = git subtree split --prefix web main
    git push origin "${tree}:refs/heads/gh-pages" --force
    Write-Host "Successfully pushed latest deals to main and gh-pages!"
} else {
    Write-Host "No changes to web/deals.json. Already up to date."
}
