#!/usr/bin/env python3
"""Split judgements CSV into train/validation sets by query_id."""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split a judgements.csv file into train/val by query_id."
    )
    parser.add_argument(
        "--input",
        default="../../ch2/evaluation/judgements.csv",
        help="Path to source judgements CSV.",
    )
    parser.add_argument(
        "--train-output",
        default="judgements_train.csv",
        help="Path to output train CSV.",
    )
    parser.add_argument(
        "--val-output",
        default="judgements_val.csv",
        help="Path to output validation CSV.",
    )
    parser.add_argument(
        "--val-fraction",
        type=float,
        default=0.2,
        help="Fraction of unique query_ids assigned to validation.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible splits.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 0.0 < args.val_fraction < 1.0:
        raise ValueError("--val-fraction must be between 0 and 1")

    input_path = Path(args.input)
    train_output_path = Path(args.train_output)
    val_output_path = Path(args.val_output)
    train_output_path.parent.mkdir(parents=True, exist_ok=True)
    val_output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise ValueError("Input CSV has no header row")
        if "query_id" not in fieldnames:
            raise ValueError("Input CSV must contain a 'query_id' column")
        rows = list(reader)

    query_ids = sorted({row["query_id"] for row in rows})
    if not query_ids:
        raise ValueError("No data rows found in input CSV")

    rng = random.Random(args.seed)
    rng.shuffle(query_ids)

    val_query_count = int(len(query_ids) * args.val_fraction)
    val_query_count = max(1, min(len(query_ids) - 1, val_query_count))
    val_query_ids = set(query_ids[:val_query_count])

    train_rows = [row for row in rows if row["query_id"] not in val_query_ids]
    val_rows = [row for row in rows if row["query_id"] in val_query_ids]

    with train_output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(train_rows)

    with val_output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(val_rows)

    print(f"Total rows: {len(rows)}")
    print(f"Total unique queries: {len(query_ids)}")
    print(f"Train unique queries: {len(query_ids) - val_query_count}")
    print(f"Val unique queries: {val_query_count}")
    print(f"Train rows: {len(train_rows)}")
    print(f"Val rows: {len(val_rows)}")
    print(f"Train output: {train_output_path}")
    print(f"Val output: {val_output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
