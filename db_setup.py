#!/usr/bin/env python3
"""Backward-compatible entrypoint for db_setup.py"""
from src.db import init_database

if __name__ == "__main__":
    init_database()
