#!/usr/bin/env python3
"""Build anchor/positive training pairs from products JSONL; output CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create JSONL pairs with anchor=ProductName and positive=Description."
    )
    parser.add_argument(
        "--input",
        default="../../ch1/dataset/products.jsonl",
        help="Path to source products JSONL file.",
    )
    parser.add_argument(
        "--output",
        default="training_pairs.csv",
        help="Path to output CSV file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    written = 0
    skipped = 0

    with input_path.open("r", encoding="utf-8") as src, output_path.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        writer = csv.writer(dst)
        writer.writerow(["anchor", "positive"])
        for line_number, line in enumerate(src, start=1):
            if not line.strip():
                continue
            total += 1

            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                print(f"Skipping invalid JSON at line {line_number}")
                continue

            fields = row.get("fields", {})
            anchor = str(fields.get("ProductName", "")).strip()
            positive = str(fields.get("Description", "")).strip()

            # skip making pairs with too short name or description
            if not anchor or not positive:
                skipped += 1
                continue
            if len(anchor) < 5 or len(positive) < 5:
                skipped += 1
                continue

            writer.writerow([anchor, positive])
            written += 1

    print(f"Input rows seen: {total}")
    print(f"Pairs written: {written}")
    print(f"Rows skipped: {skipped}")
    print(f"Output file: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
