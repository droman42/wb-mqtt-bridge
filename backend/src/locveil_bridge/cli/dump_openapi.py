"""Dump the FastAPI OpenAPI schema to a file (or stdout).

This produces the API contract snapshot that the sibling `locveil-bridge-ui` repo
consumes at build time:

  - `openapi-typescript` turns it into `src/types/api.gen.ts`
  - the device-page codegen's `StateTypeGenerator` reads device-state model
    shapes from `components.schemas` instead of importing this package and
    AST-parsing the Pydantic classes (action_plan P1 #3 / #3.5).

The schema is generated from the static route table, so no MQTT broker,
database, or device hardware is touched. Regenerate and commit the snapshot
(`openapi.json` at the repo root) whenever the API surface or any device-state
model changes.

Usage:
    locveil-openapi                  # write ./openapi.json
    locveil-openapi -o path.json     # write to a specific path
    locveil-openapi --stdout         # print to stdout
"""

import argparse
import json
import sys
from pathlib import Path

from locveil_bridge.app.bootstrap import create_app


def generate_openapi() -> dict:
    """Build the app and return its OpenAPI schema without starting services."""
    app = create_app()
    return app.openapi()


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump the OpenAPI schema for the UI build contract.")
    parser.add_argument(
        "-o",
        "--output",
        default="openapi.json",
        help="Output file path (default: ./openapi.json)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the schema to stdout instead of writing a file",
    )
    args = parser.parse_args()

    schema = generate_openapi()
    text = json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    if args.stdout:
        sys.stdout.write(text)
        return 0

    out_path = Path(args.output)
    out_path.write_text(text, encoding="utf-8")
    schema_count = len(schema.get("components", {}).get("schemas", {}))
    print(f"Wrote {out_path} ({len(schema.get('paths', {}))} paths, {schema_count} component schemas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
