# Weekly Deals & Price History Tracker

A standalone, lightweight Python engine for tracking grocery weekly circulars, recording historical sale prices, and identifying genuine bargains (All-Time Lows, cyclical promotion intervals, and price hikes) using Flipp's public flyer backend.

---

## Key Features

1. **Direct Flipp Backend API Integration**:
   - Fetches active weekly circulars via public JSON endpoints (`backflipp.wishabi.com`).
   - Zero browser automation overhead (no Selenium / Playwright / headless Chrome).
   - Fast, reliable execution (~100ms per sync).

2. **Circular Page Geometry & Front-Page Isolation**:
   - Parses multi-page flyer coordinates (`left`, `right`, `top`, `bottom`).
   - Matches deals to their flyer page based on coordinate intersection.
   - Easily filters top "Cover / Front Page" hero deals.

3. **Product Entity Normalization & Disaggregation**:
   - Disaggregates compound deal titles (e.g. *"Sugardale Bacon 12 oz., Jimmy Dean Roll Sausage 16 oz. or Hillshire Farm 12-14 oz."* under one price point).
   - Extracts numeric package sizes and units (`oz`, `lb`, `ct`, `qt`, `ltr`, etc.).
   - Computes unit prices (`$/oz` or `$/lb`).

4. **Time-Series SQLite Storage**:
   - Persists circular runs, product catalogs, and price observations.
   - Embedded database (`data/deals.db`) requiring no external server setup.

5. **Deal Intelligence & Historical Analytics**:
   - **`[🌟 ALL-TIME LOW]`**: Identifies when current price is at or below the lowest recorded sale price in history.
   - **`[🔥 BEAT AVERAGE]`**: Flags deals $\ge 15\%$ below rolling average promo prices.
   - **`[🔄 CYCLE REFRESH]`**: Tracks recurring periodic sales (e.g., bacon cycling every 4 weeks).
   - **`[⚠️ PRICE HIKE]`**: Warns if a deal is advertised as a sale but is more expensive than prior circulars.

---

## Directory Structure

```
Weekly Deals Tracker/
├── src/
│   ├── __init__.py
│   ├── fetcher.py        # Flipp API client & flyer coordinate parser
│   ├── normalizer.py     # Product entity parsing, multi-item disaggregator
│   ├── database.py       # SQLite database manager & time-series storage
│   ├── analyzer.py       # Deal intelligence & historical price trends
│   ├── video_pipeline.py # Video download, keyframe extraction & batch ingestion
│   └── cli.py            # Rich terminal CLI
├── tests/
│   ├── test_fetcher.py   # Unit tests for circular geometry & API parsing
│   ├── test_normalizer.py# Unit tests for multi-item disaggregation & unit parsing
│   ├── test_database.py  # Unit tests for SQLite storage & history queries
│   └── test_analyzer.py  # Unit tests for All-Time Low & price scoring logic
├── raw_ads/              # Historical images/PDFs/videos (gitignored)
├── data/                 # SQLite storage (deals.db) & extracted video frames
├── requirements.txt      # Dependencies
└── README.md
```

---

## Ad Ingestion & Backfill Workflows

The engine supports multiple ingestion pipelines to maintain an accurate and complete price timeline:

### 1. Live Circular Sync (Flipp API)
Ingest the active weekly ad directly from Flipp's public JSON backend. Items ingested this way are automatically tagged as **Verified / Trusted** (`is_trusted=1, source_type='flipp_api'`):
```bash
# Sync active weekly ad
python -m src.cli sync --zip 12345 --merchant "Tom Thumb"

# Sync front-page hero deals only
python -m src.cli sync --zip 12345 --front-page-only
```

### 2. Video Circular Pipeline (`src/video_pipeline.py`)
For weekly ads distributed as animated videos (e.g. Facebook / Instagram / Web MP4s):
```python
from src.video_pipeline import VideoAdPipeline

pipeline = VideoAdPipeline()

# 1. Download video
video_file = pipeline.download_video("https://example.com/ad_video.mp4")

# 2. Extract high-resolution keyframes for each page
page_frames = pipeline.extract_page_frames(video_file, flyer_id=20260401)

# 3. Ingest structured items with trust tagging
pipeline.ingest_video_deals(
    flyer_id=20260401,
    name="Easter Holiday Circular",
    valid_from="2026-04-01T00:00:00",
    valid_to="2026-04-07T23:59:59",
    pages_items=pages_data,
    is_trusted=False,
    source_type="video_pipeline_untrusted"
)
```

### 3. Historical Scans, PDFs & Vision API Ingestion (`raw_ads/`)
Historical flyer scans, screenshots, and multi-page PDFs can be placed in `raw_ads/` (gitignored). To parse and backfill historical deals from raw media, you can use an AI coding agent or a multimodal Vision API (e.g. Gemini, OpenAI, Claude):

#### A. Interactive AI Agent Workflow
When working with an AI coding agent (e.g., in your IDE or terminal), you can prompt the agent to inspect the flyer images in `raw_ads/` directly:
1. Provide the agent with the image path (e.g., `raw_ads/4-15 pg1.png`).
2. Instruct the agent to extract each promotion's deal attributes (**Item Name**, **Brand**, **Size/Unit**, **Promo Price**, **Original Price**, and **Page Number**).
3. The agent disaggregates bundled deals (e.g. multi-flavor sodas or meat bundles), normalizes units, and records them via `DealsDatabase().record_deals(deals, is_trusted=False, source_type='vision_agent_backfill')`.

#### B. Automated Scripting via Multimodal API Keys
For automated batch backfills using a Vision API (e.g., Google Gemini 1.5 Flash/Pro or OpenAI GPT-4o):
1. Add your API key to `.env` (e.g., `GEMINI_API_KEY=your_key` or `OPENAI_API_KEY=your_key`).
2. Send image bytes with a structured JSON schema prompt:
   ```python
   # Example extraction prompt schema:
   prompt = """
   Extract all grocery promotions from this weekly ad page into JSON:
   {
     "items": [
       {
         "name": "Lucerne Large Eggs 12 ct",
         "current_price": 1.99,
         "original_price": 3.49,
         "unit": "ct",
         "unit_size": 12.0,
         "page_num": 1,
         "description": "Selected varieties, Member price"
       }
     ]
   }
   """
   ```
3. Ingest the resulting items into the tracker engine:
   ```python
   from src.normalizer import ProductNormalizer
   from src.database import DealsDatabase

   normalizer = ProductNormalizer()
   db = DealsDatabase()

   normalized_deals = []
   for raw_item in extracted_items:
       deals = normalizer.disaggregate_and_normalize(raw_item)
       normalized_deals.extend(deals)

   # Mark backfilled data as untrusted until verified
   db.record_deals(normalized_deals, is_trusted=False, source_type="vision_api_backfill")
   ```

---

## Trust & Verification Management

Because historical backfills and OCR/video scans can occasionally have discrepancies, the database maintains granular trust flags:

* **View Price History with Trust Badges:**
  ```bash
  python -m src.cli history "Ground Beef"
  ```
  ```text
  --- Product: Fresh 80% Lean Ground Beef Value Pack ---
     • [2026-03-04 - 2026-03-10] Price: $3.99 (Page 1) [Untrusted / Backfill]
     • [2026-09-16 - 2026-09-22] Price: $3.99 (Page 1)
  ```

* **Strict Mode (Verified Live Data Only):**
  ```bash
  python -m src.cli history "Ground Beef" --trusted-only
  ```

* **Toggle Trust Flags:**
  ```bash
  # Mark all historical past circulars as untrusted
  python -m src.cli mark-trust untrust --all-past

  # Mark a specific flyer run as trusted
  python -m src.cli mark-trust trust --flyer-id 8131286
  ```

* **Tag Outlier / Doorbuster Deals (Excludes from standard price hike baselines):**
  ```bash
  # Tag a specific deal observation as a one-time doorbuster
  python -m src.cli mark-doorbuster tag --deal-id 2870

  # Tag an entire promotional flyer as doorbuster
  python -m src.cli mark-doorbuster tag --flyer-id 20260909
  ```

---

## Quick Start & CLI Usage

### 1. View Analyzed Deals
Display active deals in a scannable weekly digest format (defaults to **Front Page / Cover Deals**, circular-wide **Price Hike Alerts**, and inside-page **All-Time Lows**, filtering out unpriced tiles):
```bash
python -m src.cli deals
```
Available flags:
- **Show all circular items**: `python -m src.cli deals --all`
- **Filter All-Time Lows (ATL) only**: `python -m src.cli deals --atl-only`
- **Filter Price Hike warnings only**: `python -m src.cli deals --hikes-only`
- **Front page only**: `python -m src.cli deals --front-page-only`
- **Search specific product/brand**: `python -m src.cli deals -q "bacon"`
- **Include unpriced bundle tiles**: `python -m src.cli deals --include-see-ad`

### 2. Search Product History
```bash
python -m src.cli history "Bacon"
python -m src.cli history "Salmon"
```

### 3. Database Re-normalization & Catalog Reconciliation
Disaggregate compound deal records across historical circulars, link items to canonical products, and prune obsolete compound rows:
```bash
python -m src.cli renormalize
```

### 4. Export Deals to JSON or CSV
```bash
python -m src.cli export --format json --output top_deals.json
python -m src.cli export --format csv --output top_deals.csv
```

---

## Running Unit Tests

Run the full offline test suite:
```bash
python -m unittest discover -s tests -p "test_*.py"
```
