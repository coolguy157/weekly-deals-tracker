# Deploy web/ assets to GitHub Pages (gh-pages branch)
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location "$RepoRoot\deals_tracker"

Write-Host "=================================================="
Write-Host " Deploying web/ assets to gh-pages branch"
Write-Host "=================================================="

Write-Host "Splitting web subtree from main..."
$tree = git subtree split --prefix web main

Write-Host "Pushing subtree commit ($tree) to origin/gh-pages..."
git push origin "${tree}:refs/heads/gh-pages"

Write-Host "Successfully deployed latest web assets to gh-pages!"
