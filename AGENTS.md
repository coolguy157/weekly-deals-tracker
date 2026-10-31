# Deals Tracker - Agent Instructions

## Overview
Circular Ingestion & Price History Engine: Flipp API and Giant Grid fetcher, product/unit normalization, price drop analysis, historical all-time-low tracking, and static web export generation.

- Key Documentation: [deals_tracker_documentation.txt](file:///c:/Users/matth/Documents/grocery-utils/deals_tracker/deals_tracker_documentation.txt)
- Scratch Directory: `deals_tracker/scratch/`
- Remote Repository: `https://github.com/coolguy157/weekly-deals-tracker.git`

---

## Non-Negotiable Rules

1. **Dedicated Scratchpad**: Use `deals_tracker/scratch/` for one-off experimentation and diagnostics. Never use inline `python -c`. Clean up scratch files when tasks finish.
2. **Shared Database Access**: Interacts with shared database `../data/deals.db` (or local `:memory:` for testing) via `DealsDatabase` context managers.
3. **Automated Web App Deployment via GitHub Actions**:
   The web application is automatically built and deployed to GitHub Pages (`gh-pages` branch) by GitHub Actions on any push to `main` touching `web/**` (`.github/workflows/deploy_web.yml`).
   - **Do NOT manually push or split subtrees to `gh-pages`** unless GitHub Actions is unavailable or a manual recovery is explicitly requested.
   - For routine backend, normalization, or ingestion updates, simply commit and push to `origin main`.
   - Never push changes unless necessary and tested.
5. **Default to Resolutions**: When deals parsing or normalizer errors are reported, fix the issue directly in code, rerun ingestion/re-normalization if needed, and verify with tests.

---

## Key Workflows & Commands

### Sync Weekly Ads (Flipp / Tom Thumb)
```powershell
python -m deals_tracker.src.cli sync --zip 75001
```

### Sync Giant Weekly Circular
```powershell
.\deals_tracker\run_giant_sync.bat
```

### Export Deals to JSON
```powershell
python -m deals_tracker.src.cli export --format json --output web/deals.json
```

### Test Suite
```powershell
& "app_automation\.venv\Scripts\python.exe" -m pytest "deals_tracker\tests"
```
