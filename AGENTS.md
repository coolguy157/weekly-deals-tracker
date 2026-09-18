# Weekly Deals & Price History Tracker - Agent Instructions

## Documentation & Key Directories

| File / Location | Purpose & Role |
| :--- | :--- |
| **`README.md`** | **Human Guide**: Project overview, architecture summary, installation, and full CLI commands. |
| **`src/`** | **Core Codebase**: Ingestion (`fetcher.py`), entity normalizer (`normalizer.py`), SQLite storage (`database.py`), price history intelligence (`analyzer.py`), and CLI (`cli.py`). |
| **`data/`** | **SQLite Storage**: Local embedded database (`deals.db`) tracking circular snapshots, product entities, and historical price observations. |
| **`tests/`** | **Offline Test Suite**: Comprehensive unit tests with mocked API payloads and in-memory SQLite instances. |
| **`scratch/`** | **Experimental Scratchpad**: Dedicated sandbox for diagnostic and exploratory scripts. Clean up temporary files when finished. |

## Non-Negotiable Engineering Rules
1. **No Inline `python -c` Scripts**: Never execute inline ad-hoc commands with `python -c` for experimentation or testing. Always write dedicated diagnostic scripts into the `scratch/` folder.
2. **Diagnostics & Scratchpad**: Keep temporary exploration scripts inside `scratch/`. Do not inspect `scratch/` during normal context gathering, and clean up scratch files when the task is done.
3. **Coordinate-Driven Flyer Page Geometry**: When parsing Flipp circular items, always map items to flyer pages using horizontal midpoint containment (`page.left <= item_center_x <= page.right`).
4. **Preserve Comments & Docstrings**: Preserve existing comments and docstrings unless explicitly refactoring code.
5. **Database Transaction Integrity**: When executing multi-item operations, pass active SQLite connections or use unified transaction contexts to prevent nested database locks.
6. **Token-Efficient Logging & Output**: Maintain clean, structured output without superfluous banner text.

## Key Test & Verification Commands
- **Offline Unit Test Suite**: `python -m unittest discover -s tests -p "test_*.py"`
- **Live Circular Ingestion**: `python -m src.cli sync --zip 12345`
- **Front Page Deal Report**: `python -m src.cli deals --front-page-only`
- **All-Time Lows (ATL) Filter**: `python -m src.cli deals --atl-only`
- **Product History Lookup**: `python -m src.cli history "Bacon"`
- **Generic Keyword Deal Filter**: `python -m src.cli deals -q "cheese"`
- **Export Evaluated Deals**: `python -m src.cli export --format json --output deals.json`
