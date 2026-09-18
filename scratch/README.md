# Scratchpad & Diagnostic Directory

This directory (`scratch/`) is the designated sandbox for all exploratory, diagnostic, and experimental scripts.

## Rules for Agents & Developers
1. **No Ad-Hoc `python -c` Invocations**: Do not run inline `python -c` snippets in terminal sessions. All experimentation, API response inspections, and prototype logic must be written as standalone `.py` scripts inside this directory.
2. **Context Efficiency**: Do not inspect or read files inside `scratch/` during standard project context gathering.
3. **Clean Up**: Remove temporary files from `scratch/` once development and validation tasks are completed.
