#!/usr/bin/env python3
"""
UUM Document Intelligence System — Unified Automation Pipeline
Chains:
  1. Metadata Extraction, OCR & Tracker Sorter (sort.py)
  2. Incremental Document Chunking & Vector Search Indexing (ingest.py)

Usage:
    python3 pipeline.py [--clean] [--force-reembed] [--force-ocr]
"""

import sys
import time
import argparse
from src.tracker_sorter import main as run_sorter
from src.ingestion import run_ingestion

def main():
    parser = argparse.ArgumentParser(
        description="Unified Automation Pipeline for UUM Circular & Project Document Intelligence System"
    )
    parser.add_argument("--clean", action="store_true", help="Remove Windows artifact files (:Zone.Identifier / desktop.ini)")
    parser.add_argument("--force-ocr", action="store_true", help="Force OCR re-extraction on all documents")
    parser.add_argument("--force-reembed", action="store_true", help="Force re-generation of all vector embeddings")
    args = parser.parse_args()

    start_time = time.time()
    print("\n" + "=" * 75)
    print("  🚀 UUM DOCUMENT INTELLIGENCE — UNIFIED AUTOMATION PIPELINE")
    print("=" * 75)

    print("\n[STEP 1/2] Scanning circular_forms/ and Updating Master Tracker...")
    sys_argv_backup = sys.argv
    sorter_args = ["sort.py"]
    if args.clean:
        sorter_args.append("--clean")
    if args.force_ocr:
        sorter_args.append("--force-ocr")
    sys.argv = sorter_args

    try:
        run_sorter()
    finally:
        sys.argv = sys_argv_backup

    print("\n[STEP 2/2] Updating Search Index & Vector Embeddings...")
    run_ingestion(force_reembed=args.force_reembed)

    elapsed = time.time() - start_time
    print("\n" + "=" * 75)
    print(f"  ✨ PIPELINE COMPLETE IN {elapsed:.1f} SECONDS!")
    print("  The knowledge base is up to date and ready for queries via ask.py")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    main()

