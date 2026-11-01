#!/usr/bin/env python3
"""Backward-compatible entrypoint for ingest_to_postgres.py"""
from src.ingestion import run_ingestion

if __name__ == "__main__":
    run_ingestion()
