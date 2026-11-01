#!/usr/bin/env python3
"""
UUM Tracker Auto-Sorter CLI Entrypoint
Usage:
    python3 sort.py [--clean] [--force-ocr]
"""

from src.tracker_sorter import main

if __name__ == "__main__":
    main()
