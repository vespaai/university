#!/usr/bin/env python3
"""Build A-training pairs from train judgements (query -> product text)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def stable_seed(seed: int, key: str) -> int:
    raw = f"{seed}:{key}".encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create query->product-text pairs from training judgements."
    )
    parser.add_argument(
        "--judgements",
        default="judgements_train.csv",
        help="Training judgements CSV path.",
    )
    parser.add_argument(
        "--queries",
        default="../../ch2/evaluation/queries.csv",
        help="Queries CSV path.",
    )
    parser.add_argument(
        "--products",
        default="../../ch1/dataset/products.jsonl",
        help="Products JSONL path.",
    )
    parser.add_argument(
        "--output",
        default="train_pairs.jsonl",
        help="Output JSONL path with anchor/positive pairs.",
    )
    parser.add_argument(
        "--metadata-output",
        default="train_pairs_metadata.csv",
        help="Output CSV path for pair metadata.",
    )
    parser.add_argument(
        "--positive-rating",
        type=int,
        default=3,
        help="Judgement rating to treat as positive.",
    )
    parser.add_argument(
        "--min-query-chars",
        type=int,
        default=3,
        help="Minimum query length in characters.",
    )
    parser.add_argument(
        "--min-title-chars",
        type=int,
        default=8,
        help="Minimum product title length in characters.",
    )
    parser.add_argument(
        "--min-description-chars",
        type=int,
        default=40,
        help="Minimum product description length in characters.",
    )
    parser.add_argument(
        "--max-pairs-per-query",
        type=int,
        default=50,
        help="Maximum emitted pairs per query_id. Use 0 for unlimited.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed used for deterministic per-query shuffling.",
    )
    return parser.parse_args()


def load_queries(path: Path) -> dict[str, str]:
    query_map: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "query_id" not in reader.fieldnames:
            raise ValueError("queries CSV must contain query_id")
        if "query_text" not in reader.fieldnames:
            raise ValueError("queries CSV must contain query_text")
        for row in reader:
            query_id = str(row["query_id"]).strip()
            query_text = normalize_text(str(row["query_text"]).strip())
            if query_id:
                query_map[query_id] = query_text
    return query_map


def load_products(path: Path) -> dict[str, tuple[str, str]]:
    product_map: dict[str, tuple[str, str]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                print(f"Skipping invalid products JSON at line {line_number}")
                continue
            fields = row.get("fields", {})
            document_id = str(fields.get("ProductID", "")).strip()
            if not document_id:
                continue
            title = normalize_text(str(fields.get("ProductName", "")).strip())
            description = normalize_text(str(fields.get("Description", "")).strip())
            product_map[document_id] = (title, description)
    return product_map


def main() -> int:
    args = parse_args()
    judgements_path = Path(args.judgements)
    queries_path = Path(args.queries)
    products_path = Path(args.products)
    output_path = Path(args.output)
    metadata_output_path = Path(args.metadata_output)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_output_path.parent.mkdir(parents=True, exist_ok=True)

    query_map = load_queries(queries_path)
    product_map = load_products(products_path)

    candidates_by_query: dict[str, list[dict[str, str]]] = defaultdict(list)

    seen_judgements = 0
    selected_positive_rows = 0
    skipped_missing_query = 0
    skipped_short_query = 0
    skipped_missing_product = 0
    skipped_invalid_rating = 0
    skipped_empty_title = 0
    skipped_short_title = 0
    skipped_empty_description = 0
    skipped_short_description = 0

    with judgements_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"query_id", "document_id", "rating"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("judgements CSV must contain query_id, document_id, rating")

        for row in reader:
            seen_judgements += 1
            query_id = str(row["query_id"]).strip()
            document_id = str(row["document_id"]).strip()

            try:
                rating = int(str(row["rating"]).strip())
            except ValueError:
                skipped_invalid_rating += 1
                continue

            if rating != args.positive_rating:
                continue
            selected_positive_rows += 1

            query_text = query_map.get(query_id, "")
            if not query_text:
                skipped_missing_query += 1
                continue
            if len(query_text) < args.min_query_chars:
                skipped_short_query += 1
                continue

            product = product_map.get(document_id)
            if product is None:
                skipped_missing_product += 1
                continue

            title, description = product
            if not title:
                skipped_empty_title += 1
            elif len(title) < args.min_title_chars:
                skipped_short_title += 1
            else:
                candidates_by_query[query_id].append(
                    {
                        "anchor": query_text,
                        "positive": title,
                        "query_id": query_id,
                        "document_id": document_id,
                        "field": "title",
                        "rating": str(rating),
                    }
                )

            if not description:
                skipped_empty_description += 1
            elif len(description) < args.min_description_chars:
                skipped_short_description += 1
            else:
                candidates_by_query[query_id].append(
                    {
                        "anchor": query_text,
                        "positive": description,
                        "query_id": query_id,
                        "document_id": document_id,
                        "field": "description",
                        "rating": str(rating),
                    }
                )

    emitted_pairs = 0
    duplicate_pairs_skipped = 0
    cap_skipped = 0
    seen_pairs: set[tuple[str, str]] = set()

    with output_path.open("w", encoding="utf-8") as output_file, metadata_output_path.open(
        "w", encoding="utf-8", newline=""
    ) as meta_file:
        meta_fieldnames = [
            "query_id",
            "document_id",
            "field",
            "rating",
            "anchor_chars",
            "positive_chars",
        ]
        meta_writer = csv.DictWriter(meta_file, fieldnames=meta_fieldnames)
        meta_writer.writeheader()

        for query_id in sorted(candidates_by_query):
            candidates = candidates_by_query[query_id]
            query_rng = random.Random(stable_seed(args.seed, query_id))
            query_rng.shuffle(candidates)

            if args.max_pairs_per_query > 0 and len(candidates) > args.max_pairs_per_query:
                cap_skipped += len(candidates) - args.max_pairs_per_query
                candidates = candidates[: args.max_pairs_per_query]

            for candidate in candidates:
                pair_key = (candidate["anchor"], candidate["positive"])
                if pair_key in seen_pairs:
                    duplicate_pairs_skipped += 1
                    continue
                seen_pairs.add(pair_key)

                output_file.write(
                    json.dumps(
                        {"anchor": candidate["anchor"], "positive": candidate["positive"]},
                        ensure_ascii=False,
                    )
                    + "\n"
                )

                meta_writer.writerow(
                    {
                        "query_id": candidate["query_id"],
                        "document_id": candidate["document_id"],
                        "field": candidate["field"],
                        "rating": candidate["rating"],
                        "anchor_chars": len(candidate["anchor"]),
                        "positive_chars": len(candidate["positive"]),
                    }
                )
                emitted_pairs += 1

    duplicate_query_texts = defaultdict(int)
    for text in query_map.values():
        duplicate_query_texts[text] += 1
    repeated_query_text_count = sum(
        1 for count in duplicate_query_texts.values() if count > 1
    )

    print(f"Judgement rows seen: {seen_judgements}")
    print(f"Positive judgement rows (rating={args.positive_rating}): {selected_positive_rows}")
    print(f"Queries loaded: {len(query_map)}")
    print(f"Products loaded: {len(product_map)}")
    print(f"Candidate pairs before cap/dedupe: {sum(len(v) for v in candidates_by_query.values())}")
    print(f"Pairs skipped due to per-query cap: {cap_skipped}")
    print(f"Pairs skipped as duplicates: {duplicate_pairs_skipped}")
    print(f"Final pairs emitted: {emitted_pairs}")
    print(f"Queries with candidates: {len(candidates_by_query)}")
    print(f"Duplicate query_text values across query_id: {repeated_query_text_count}")
    print(f"Skipped missing query: {skipped_missing_query}")
    print(f"Skipped short query: {skipped_short_query}")
    print(f"Skipped missing product: {skipped_missing_product}")
    print(f"Skipped invalid rating: {skipped_invalid_rating}")
    print(f"Skipped empty title: {skipped_empty_title}")
    print(f"Skipped short title: {skipped_short_title}")
    print(f"Skipped empty description: {skipped_empty_description}")
    print(f"Skipped short description: {skipped_short_description}")
    print(f"Output pairs: {output_path}")
    print(f"Output metadata: {metadata_output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
