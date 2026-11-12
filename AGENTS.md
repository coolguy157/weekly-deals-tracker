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
3. **GitHub Pages Deployment via `gh-pages`**:
   The static web frontend is hosted on GitHub Pages from the **`gh-pages` branch** (where assets live at the root).
   - **Automated Workflow**: `.github/workflows/deploy_web.yml` triggers on any push to `main` modifying `web/**` (configured with `fetch-depth: 0` and `peaceiris/actions-gh-pages`).
   - **Direct Deploy / Verification**: When deploying UI updates directly or verifying, run:
     ```powershell
     .\deals_tracker\scripts\deploy_web.ps1
     ```
     Or execute the subtree push manually:
     ```powershell
     cd deals_tracker
     $tree = git subtree split --prefix web main
     git push origin "${tree}:refs/heads/gh-pages"
     ```
   - Never push untested web changes.
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
