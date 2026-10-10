# Deals Tracker - Agent Instructions & Workflows

## Overview
Circular Ingestion & Price History Engine: Flipp API and Giant Grid fetcher, product/unit normalization, price drop analysis, historical all-time-low tracking, and static web app export.

## Key Rules & Workflows
1. **Dedicated Scratchpad**: Use `deals_tracker/scratch/` for one-off experimentation and diagnostics. Never use inline `python -c`. Clean up scratch files when tasks finish.
2. **Shared Database**: Interacts with shared database `../data/deals.db` (or local `:memory:` for testing) via `DealsDatabase` context managers.
3. **Web App Deployment to GitHub Pages**:
   The live web application is hosted via GitHub Pages from the root of the `gh-pages` branch. When web assets (`deals_tracker/web/`) or `deals.json` are updated, deploy them to GitHub Pages by extracting the `web` subtree from `main`:
   ```powershell
   # In deals_tracker directory:
   $subtree = (git subtree split --prefix web main).Trim()
   git push origin "${subtree}:refs/heads/gh-pages" --force
   ```

## Test Commands
- **Run Deals Tracker Test Suite**:
  `pytest tests/`
- **Sync Current Weekly Ad**:
  `python -m src.cli sync --zip 75001`
- **Export Deals to JSON**:
  `python -m src.cli export --merchant Giant --format json --output web/deals.json`
