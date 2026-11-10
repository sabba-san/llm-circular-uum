#!/usr/bin/env python3
"""
UUM Document Ingestion & Chunking CLI Entrypoint
Usage:
    python3 ingest.py [--circulars-only] [--college-only] [--force-reembed]
"""

import argparse
from src.ingestion import run_ingestion as run_circular_ingestion
from src.college_ingestion import run_college_ingestion

def main():
    parser = argparse.ArgumentParser(
        description="Ingest circulars, academic documents & forms into PostgreSQL / SQLite knowledge base."
    )
    parser.add_argument("--circulars-only", action="store_true", help="Ingest only administrative circulars and forms")
    parser.add_argument("--college-only", action="store_true", help="Ingest only college academic documents and forms")
    parser.add_argument("--force-reembed", action="store_true", help="Force re-generation of all vector embeddings")
    args = parser.parse_args()

    if args.circulars_only:
        print(">>> Ingesting Administrative Circulars & Forms...")
        run_circular_ingestion(force_reembed=args.force_reembed)
    elif args.college_only:
        print(">>> Ingesting College Academic Documents & Forms...")
        run_college_ingestion(force_reembed=args.force_reembed)
    else:
        print(">>> [1/2] Ingesting Administrative Circulars & Forms...")
        run_circular_ingestion(force_reembed=args.force_reembed)
        print("\n>>> [2/2] Ingesting College Academic Documents & Forms...")
        run_college_ingestion(force_reembed=args.force_reembed)

if __name__ == "__main__":
    main()
