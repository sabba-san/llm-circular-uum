#!/usr/bin/env python3
"""
UUM Document Intelligence System — Unified Automation Pipeline
Chains:
  1. Metadata Extraction, OCR & Tracker Sorter (sort.py)
  2. Incremental Document Chunking & Vector Search Indexing (ingest.py)

Usage:
    python3 pipeline.py [--all | --circulars-only | --college-only] [--clean] [--force-reembed] [--force-ocr]
"""

import time
import argparse
from src.tracker_sorter import run_sorter
from src.college_tracker import run_college_tracker
from src.ingestion import run_ingestion as run_circular_ingestion
from src.college_ingestion import run_college_ingestion


def main():
    parser = argparse.ArgumentParser(
        description="Unified Automation Pipeline for UUM Circular & Project Document Intelligence System"
    )
    scope_group = parser.add_mutually_exclusive_group()
    scope_group.add_argument("--all", action="store_true", help="Sync both PTJ circulars and college documents (default)")
    scope_group.add_argument("--circulars-only", action="store_true", help="Sync only PTJ circulars and forms")
    scope_group.add_argument("--college-only", action="store_true", help="Sync only college academic documents and forms")
    parser.add_argument("--clean", action="store_true", help="Remove Windows artifact files (:Zone.Identifier / desktop.ini)")
    parser.add_argument("--force-ocr", action="store_true", help="Force OCR re-extraction on all documents")
    parser.add_argument("--force-reembed", action="store_true", help="Force re-generation of all vector embeddings")
    args = parser.parse_args()

    run_circulars = not args.college_only
    run_college = not args.circulars_only

    start_time = time.time()
    print("\n" + "=" * 75)
    print("  🚀 UUM DOCUMENT INTELLIGENCE — UNIFIED AUTOMATION PIPELINE")
    print("=" * 75)

    print("\n[STEP 1/2] Scanning Documents & Updating Master Trackers...")
    if run_circulars:
        print("  -> Updating PTJ Circulars & Forms Tracker...")
        run_sorter(clean=args.clean, force_ocr=args.force_ocr)

    if run_college:
        print("  -> Updating College Documents & Forms Tracker...")
        run_college_tracker()

    print("\n[STEP 2/2] Updating Search Index & Vector Embeddings...")
    if run_circulars:
        print("  -> Ingesting Circulars & Financial Guidelines...")
        run_circular_ingestion(force_reembed=args.force_reembed)
    if run_college:
        print("  -> Ingesting College Academic Handbooks, Catalogues & Forms...")
        run_college_ingestion(force_reembed=args.force_reembed)

    elapsed = time.time() - start_time
    print("\n" + "=" * 75)
    print(f"  ✨ PIPELINE COMPLETE IN {elapsed:.1f} SECONDS!")
    print("  The knowledge base is up to date and ready for queries via ask.py")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    main()

