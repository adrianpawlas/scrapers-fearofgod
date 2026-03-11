#!/usr/bin/env python3
"""
CLI entrypoint for manual runs.
  python run.py              # full run
  python run.py --dry-run    # scrape only, no DB
  python run.py --limit=5    # process first 5 products (for testing)
"""
from main import run
import sys

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    limit = None
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=")[1])
            except ValueError:
                pass
    run(dry_run=dry, limit=limit)
