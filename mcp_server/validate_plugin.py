#!/usr/bin/env python3
"""
Validates a chart plugin JSON file before submission.

Usage:
    python mcp_server/validate_plugin.py chart_plugins/my_chart.json
    python mcp_server/validate_plugin.py chart_plugins/   # validate all plugins
"""

import json
import re
import sys
from pathlib import Path

REQUIRED_FIELDS = ["type", "promptDescription", "renderScript"]

ERRORS = []
WARNINGS = []


def error(msg: str):
    ERRORS.append(f"  ERROR: {msg}")


def warn(msg: str):
    WARNINGS.append(f"  WARN:  {msg}")


def validate_file(path: Path) -> bool:
    ERRORS.clear()
    WARNINGS.clear()

    # 1. Valid JSON
    try:
        plugin = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"\n{path.name}")
        print(f"  ERROR: Invalid JSON — {e}")
        return False

    # 2. Required fields present
    for field in REQUIRED_FIELDS:
        if field not in plugin:
            error(f"Missing required field: '{field}'")
        elif not isinstance(plugin[field], str):
            error(f"Field '{field}' must be a string, got {type(plugin[field]).__name__}")
        elif not plugin[field].strip():
            error(f"Field '{field}' must not be empty")

    if ERRORS:
        _print_result(path)
        return False

    ptype = plugin["type"]
    desc = plugin["promptDescription"]
    script = plugin["renderScript"]

    # 3. type: lowercase, no spaces
    if not re.match(r'^[a-z0-9][a-z0-9\-]*$', ptype):
        error(f"'type' must be lowercase alphanumeric with optional hyphens, got: '{ptype}'")

    # 4. type should match filename (ignoring leading underscore for template)
    expected_stem = path.stem
    if not expected_stem.startswith("_") and ptype != expected_stem:
        warn(f"'type' value '{ptype}' does not match filename '{expected_stem}.json'")

    # 5. promptDescription should reference the type name
    if f"**{ptype}**" not in desc:
        warn(f"'promptDescription' should contain '**{ptype}**' (e.g. '- **{ptype}** — ...')")

    if "Spec:" not in desc and "spec:" not in desc:
        warn("'promptDescription' should include a 'Spec:' example showing the spec format")

    # 6. renderScript basic checks
    stripped = script.strip()
    if not stripped.startswith("function"):
        error("'renderScript' must start with 'function'")

    if stripped.count("{") != stripped.count("}"):
        error("'renderScript' has mismatched braces { }")

    if len(script) < 50:
        warn("'renderScript' looks very short — is it complete?")

    if "wrap" not in script:
        warn("'renderScript' does not reference 'wrap' — the chart may not render into the container")

    if "spec" not in script:
        warn("'renderScript' does not reference 'spec' — the chart may ignore all data")

    # 7. Check for common renderScript issues
    if "document.write" in script:
        error("'renderScript' must not use document.write()")

    if re.search(r'\balert\s*\(', script):
        warn("'renderScript' contains alert() — remove before submitting")

    if "localhost" in script or "127.0.0.1" in script:
        error("'renderScript' references localhost — use a CDN URL instead")

    # 8. exampleSpec (optional) — a small, real, inline spec the playground can render
    if "exampleSpec" in plugin:
        ex = plugin["exampleSpec"]
        if not isinstance(ex, dict):
            error(f"'exampleSpec' must be an object, got {type(ex).__name__}")
        else:
            if ex.get("type") != ptype:
                error(f"'exampleSpec.type' ('{ex.get('type')}') must equal the plugin type '{ptype}'")
            # SQL-only specs can't render in playground.html (no database in the browser)
            if "sql" in ex and not any(k in ex for k in ("data", "rows", "nodes", "links", "events",
                                                          "datasets", "labels", "snapshots", "value")):
                warn("'exampleSpec' has only a 'sql' field — playground.html can't render it; "
                     "provide an inline-data example instead")

    _print_result(path)
    return len(ERRORS) == 0


def _print_result(path: Path):
    status = "PASS" if not ERRORS else "FAIL"
    total = len(ERRORS) + len(WARNINGS)
    print(f"\n{path.name}  [{status}]")
    for msg in ERRORS + WARNINGS:
        print(msg)
    if total == 0:
        print("  OK — no issues found")


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_plugin.py <plugin.json | chart_plugins/>")
        sys.exit(1)

    target = Path(sys.argv[1])

    if target.is_dir():
        files = sorted(f for f in target.glob("*.json") if not f.stem.startswith("_"))
        if not files:
            print(f"No plugin JSON files found in {target}")
            sys.exit(1)
        results = [validate_file(f) for f in files]
        passed = sum(results)
        print(f"\n{'-'*40}")
        print(f"Result: {passed}/{len(results)} plugins passed")
        sys.exit(0 if all(results) else 1)
    elif target.is_file():
        ok = validate_file(target)
        sys.exit(0 if ok else 1)
    else:
        print(f"Path not found: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
