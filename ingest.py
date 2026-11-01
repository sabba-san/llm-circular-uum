#!/usr/bin/env python3
"""
UUM Document Ingestion & Chunking CLI Entrypoint
Usage:
    python3 ingest.py
"""

import argparse
from src.ingestion import run_ingestion

def main():
    parser = argparse.ArgumentParser(
        description="Ingest circulars & forms from tracker into PostgreSQL / SQLite knowledge base."
    )
    parser.parse_args()
    run_ingestion()

if __name__ == "__main__":
    main()
