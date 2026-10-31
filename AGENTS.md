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
3. **Push to `origin main` (No `gh-pages` Redeploy for Backend/Normalizer Updates)**:
   When making changes to analysis, normalization, or ingestion, commit and push to `origin main`. Do NOT deploy to `gh-pages` via subtree split for routine backend updates.
4. **Deploying Live Web App to GitHub Pages**:
   Only redeploy to `gh-pages` when explicit live website UI assets (`deals_tracker/web/` or root `web/`) or web exports are requested:
   ```powershell
   cd deals_tracker
   $subtree = (git subtree split --prefix web main).Trim()
   git push origin "${subtree}:refs/heads/gh-pages" --force
   ```
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
