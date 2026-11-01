#!/usr/bin/env python3
"""
UUM Assistant CLI Entrypoint
Usage:
    python3 ask.py "query"
    python3 ask.py --interactive
"""

import sys
import argparse
from src.search import UUMAssistant, print_result

def main():
    parser = argparse.ArgumentParser(description="UUM Circular & Project Document Intelligence Assistant")
    parser.add_argument("query", nargs="*", help="Question in Bahasa Melayu or English")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive chat mode")
    args = parser.parse_args()

    assistant = UUMAssistant()
    if args.interactive or not args.query:
        print("\n=== UUM Circular & Project Document Intelligence Assistant (CLI) ===")
        print("Tanya sebarang soalan mengenai pekeliling, borang, dan prosedur UUM.")
        print("Taip 'exit' atau 'quit' untuk tamat.\n")
        while True:
            try:
                q = input("Soalan UUM > ").strip()
                if q.lower() in ["exit", "quit", "q"]:
                    break
                if not q:
                    continue
                res = assistant.ask(q)
                print_result(res)
            except (KeyboardInterrupt, EOFError):
                break
    else:
        res = assistant.ask(" ".join(args.query))
        print_result(res)

if __name__ == "__main__":
    main()
