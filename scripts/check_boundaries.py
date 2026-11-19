#!/usr/bin/env python3
"""
Deterministic architectural boundary & anti-pattern checker for llm_uum.

Rules:
  B001: No direct sqlite3 / psycopg2 imports in web/UI layers (web_app.py, app.py).
  B002: No web/UI framework imports (starlette, uvicorn, streamlit) inside src/.
  B003: No global sys.argv mutation outside tests/.
  B004: No silent 'except Exception: pass' in src/, web_app.py, or app.py.
  B005: Every subprocess.run(...) call must pass an explicit timeout= keyword.
  B006: Frontend JavaScript syntax check via `node --check static/app.js`.
"""

import ast
import os
import shutil
import subprocess
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_UI_FILES = {"web_app.py", "app.py"}
DB_DRIVERS = {"sqlite3", "psycopg2"}
UI_FRAMEWORKS = {"starlette", "uvicorn", "streamlit"}


def iter_python_files():
    targets = []
    for root_file in ("web_app.py", "app.py", "pipeline.py", "ingest.py", "ask.py", "sort.py"):
        p = os.path.join(ROOT_DIR, root_file)
        if os.path.isfile(p):
            targets.append(root_file)
    for folder in ("src", "eval", "scripts"):
        d = os.path.join(ROOT_DIR, folder)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.endswith(".py"):
                targets.append(os.path.join(folder, name))
    return targets


def check_file(rel_path):
    errors = []
    full_path = os.path.join(ROOT_DIR, rel_path)
    with open(full_path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, filename=rel_path)

    is_web_ui = rel_path in WEB_UI_FILES
    is_core_src = rel_path.startswith("src" + os.sep) or rel_path.startswith("src/")

    for node in ast.walk(tree):
        # B001 & B002: Import boundary checks
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif node.module:
                modules = [node.module.split(".")[0]]
            for mod in modules:
                if is_web_ui and mod in DB_DRIVERS:
                    errors.append(
                        f"B001 {rel_path}:{node.lineno}: Direct DB driver import '{mod}' in web/UI layer. "
                        f"Move SQL queries into a helper in src/db.py instead of querying the DB from route/UI code."
                    )
                if is_core_src and mod in UI_FRAMEWORKS:
                    errors.append(
                        f"B002 {rel_path}:{node.lineno}: Web/UI framework import '{mod}' inside core package src/. "
                        f"Keep src/ UI-agnostic; return plain data structures and handle HTTP/UI in web_app.py or app.py."
                    )

        # B003: Global sys.argv mutation
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "sys"
                    and target.attr == "argv"
                ):
                    errors.append(
                        f"B003 {rel_path}:{node.lineno}: Global sys.argv mutation is forbidden. "
                        f"Expose a typed function with explicit parameters in the target module instead of faking CLI argv."
                    )

        # B004: Silent 'except Exception: pass'
        if isinstance(node, ast.ExceptHandler) and (is_core_src or is_web_ui):
            is_broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id == "Exception")
            is_pass_only = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
            if is_broad and is_pass_only:
                errors.append(
                    f"B004 {rel_path}:{node.lineno}: Silent 'except Exception: pass' hides runtime failures. "
                    f"Catch a narrow exception type and log with logger.debug/warning or handle the fallback explicitly."
                )

        # B005: subprocess.run() requires timeout=
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
                and node.func.attr == "run"
            ):
                has_timeout = any(kw.arg == "timeout" for kw in node.keywords)
                if not has_timeout:
                    errors.append(
                        f"B005 {rel_path}:{node.lineno}: subprocess.run() called without timeout=. "
                        f"Pass timeout=<seconds> (e.g., timeout=20) so malformed PDFs or subprocesses cannot hang."
                    )

    return errors


def check_js_syntax():
    node = shutil.which("node")
    if not node:
        nvm_node = "/home/abbas/.nvm/versions/node/v26.1.0/bin/node"
        node = nvm_node if os.path.isfile(nvm_node) and os.access(nvm_node, os.X_OK) else None
    if not node:
        return []
    js_file = os.path.join(ROOT_DIR, "static", "app.js")
    proc = subprocess.run([node, "--check", js_file], capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout).strip().splitlines()[0] if (proc.stderr or proc.stdout).strip() else "syntax error"
        return [f"B006 static/app.js: JavaScript syntax error ({msg}). Fix syntax before restarting Docker."]
    return []


def main():
    all_errors = []
    for rel_path in iter_python_files():
        all_errors.extend(check_file(rel_path))
    all_errors.extend(check_js_syntax())

    if all_errors:
        for err in all_errors:
            print(err)
        sys.exit(1)
    print(f"All boundary checks passed (B001-B006 across {len(iter_python_files())} Python files + static/app.js)")


if __name__ == "__main__":
    main()
