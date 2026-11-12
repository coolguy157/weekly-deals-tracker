# Web Frontend - Agent Instructions

## Overview
Static single-page web app for searching, filtering, and browsing grocery circular deals, price histories, and coupon stacks across Tom Thumb and Giant stores. Hosted via GitHub Pages (`gh-pages`).

- Root Directory: `web/` (mirrored / synced with `deals_tracker/web/`)
- Main Components:
  - `index.html`: Web layout, search UI, filter bars, and modal views.
  - `app.js`: Client-side deal filtering, search, pagination, sort logic, and deal card rendering.
  - `styles.css`: Responsive layout, card designs, dark mode, and UI styling.
  - `deals.json`: Ingested deals dataset generated from `deals_tracker` exports.

---

## Non-Negotiable Rules

1. **GitHub Pages Deployment via `gh-pages`**:
   The web application is hosted from the **`gh-pages`** branch (where assets live at the root).
   - Deployment occurs via GitHub Actions (`.github/workflows/deploy_web.yml`) on pushes to `main` modifying `web/**`.
   - Direct local deployment / manual recovery can be run at any time via:
     ```powershell
     .\deals_tracker\scripts\deploy_web.ps1
     ```
     which isolates the `web/` subtree and pushes directly to `origin/gh-pages`.
2. **Push Only When Necessary**:
   Only commit and push web changes to `main` and `gh-pages` when verified and ready for live production. Avoid unnecessary or untested pushes.
3. **No Heavy Runtime Dependencies**: The web client remains vanilla, high-performance HTML/CSS/JS without external build steps or heavy frameworks. Ensure compatibility across modern mobile and desktop browsers.
