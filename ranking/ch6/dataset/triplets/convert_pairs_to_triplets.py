#!/usr/bin/env python3
"""Convert A pairs into triplets using query-specific rating=0 negatives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
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
        description="Convert query-positive pairs into query-positive-negative triplets."
    )
    parser.add_argument(
        "--pairs",
        default="../train_pairs.jsonl",
        help="Input JSONL with anchor/positive pairs.",
    )
    parser.add_argument(
        "--pairs-metadata",
        default="../train_pairs_metadata.csv",
        help="Metadata CSV aligned line-by-line with --pairs.",
    )
    parser.add_argument(
        "--judgements",
        default="../judgements_train.csv",
        help="Training judgements CSV used to find rating=0 negatives.",
    )
    parser.add_argument(
        "--products",
        default="../../../ch1/dataset/products.jsonl",
        help="Products JSONL used to fetch negative text.",
    )
    parser.add_argument(
        "--output",
        default="train_triplets.jsonl",
        help="Output triplets JSONL path.",
    )
    parser.add_argument(
        "--metadata-output",
        default="train_triplets_metadata.csv",
        help="Output triplet metadata CSV path.",
    )
    parser.add_argument(
        "--negative-rating",
        type=int,
        default=0,
        help="Judgement rating value used as negatives.",
    )
    parser.add_argument(
        "--min-title-chars",
        type=int,
        default=8,
        help="Minimum chars for negative title text.",
    )
    parser.add_argument(
        "--min-description-chars",
        type=int,
        default=40,
        help="Minimum chars for negative description text.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for deterministic negative ordering.",
    )
    return parser.parse_args()


def load_products(path: Path) -> dict[str, tuple[str, str]]:
    products: dict[str, tuple[str, str]] = {}
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
            products[document_id] = (title, description)
    return products


def load_negative_doc_ids(path: Path, negative_rating: int) -> dict[str, list[str]]:
    negatives: dict[str, list[str]] = defaultdict(list)
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"query_id", "document_id", "rating"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("Judgements CSV must contain query_id, document_id, rating")
        for row in reader:
            try:
                rating = int(str(row["rating"]).strip())
            except ValueError:
                continue
            if rating != negative_rating:
                continue
            query_id = str(row["query_id"]).strip()
            document_id = str(row["document_id"]).strip()
            if query_id and document_id:
                negatives[query_id].append(document_id)

    # Deduplicate while preserving original order.
    for query_id, docs in negatives.items():
        negatives[query_id] = list(dict.fromkeys(docs))
    return negatives


def is_valid_text(field: str, text: str, min_title: int, min_description: int) -> bool:
    if not text:
        return False
    if field == "title":
        return len(text) >= min_title
    if field == "description":
        return len(text) >= min_description
    return False


def get_negative_text(
    field: str,
    product_texts: tuple[str, str],
) -> str:
    title, description = product_texts
    if field == "title":
        return title
    if field == "description":
        return description
    return ""


def load_pairs(path: Path) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in pairs file at line {line_number}") from exc
            anchor = normalize_text(str(row.get("anchor", "")).strip())
            positive = normalize_text(str(row.get("positive", "")).strip())
            pairs.append({"anchor": anchor, "positive": positive})
    return pairs


def load_pairs_metadata(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"query_id", "document_id", "field", "rating"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(
                "Pairs metadata CSV must contain query_id, document_id, field, rating"
            )
        return [row for row in reader]


def main() -> int:
    args = parse_args()
    pairs_path = Path(args.pairs)
    pairs_meta_path = Path(args.pairs_metadata)
    judgements_path = Path(args.judgements)
    products_path = Path(args.products)
    output_path = Path(args.output)
    metadata_output_path = Path(args.metadata_output)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_output_path.parent.mkdir(parents=True, exist_ok=True)

    products = load_products(products_path)
    negatives_by_query = load_negative_doc_ids(judgements_path, args.negative_rating)
    pairs = load_pairs(pairs_path)
    pairs_meta = load_pairs_metadata(pairs_meta_path)

    if len(pairs) != len(pairs_meta):
        raise ValueError(
            "Pairs and metadata line counts differ: "
            f"{len(pairs)} vs {len(pairs_meta)}"
        )

    by_query_indices: dict[str, list[int]] = defaultdict(list)
    for index, meta in enumerate(pairs_meta):
        query_id = str(meta["query_id"]).strip()
        by_query_indices[query_id].append(index)

    neg_order_by_query: dict[str, list[str]] = {}
    for query_id, docs in negatives_by_query.items():
        ordered = docs[:]
        rng = random.Random(stable_seed(args.seed, query_id))
        rng.shuffle(ordered)
        neg_order_by_query[query_id] = ordered

    used_negative_docs_by_query: dict[str, set[str]] = defaultdict(set)
    recycle_pointer_by_query_field: dict[tuple[str, str], int] = defaultdict(int)

    total_pairs = len(pairs)
    emitted_triplets = 0
    recycled_negatives = 0
    dropped_no_negative_docs_for_query = 0
    dropped_no_eligible_negative_for_pair = 0
    dropped_unknown_field = 0
    dropped_missing_negative_product = 0
    dropped_invalid_negative_text = 0

    with output_path.open("w", encoding="utf-8") as out_f, metadata_output_path.open(
        "w", encoding="utf-8", newline=""
    ) as meta_f:
        meta_writer = csv.DictWriter(
            meta_f,
            fieldnames=[
                "query_id",
                "pos_document_id",
                "neg_document_id",
                "field",
                "neg_recycled",
                "anchor_chars",
                "positive_chars",
                "negative_chars",
            ],
        )
        meta_writer.writeheader()

        for query_id in sorted(by_query_indices):
            pair_indices = by_query_indices[query_id]
            neg_doc_ids = neg_order_by_query.get(query_id, [])
            if not neg_doc_ids:
                dropped_no_negative_docs_for_query += len(pair_indices)
                continue

            for idx in pair_indices:
                pair = pairs[idx]
                meta = pairs_meta[idx]
                field = str(meta["field"]).strip()
                pos_document_id = str(meta["document_id"]).strip()

                if field not in {"title", "description"}:
                    dropped_unknown_field += 1
                    continue

                eligible_docs_all: list[str] = []
                eligible_docs_unused: list[str] = []

                for neg_doc_id in neg_doc_ids:
                    if neg_doc_id == pos_document_id:
                        continue
                    product = products.get(neg_doc_id)
                    if product is None:
                        continue
                    neg_text = get_negative_text(field, product)
                    if not is_valid_text(
                        field,
                        neg_text,
                        args.min_title_chars,
                        args.min_description_chars,
                    ):
                        continue
                    eligible_docs_all.append(neg_doc_id)
                    if neg_doc_id not in used_negative_docs_by_query[query_id]:
                        eligible_docs_unused.append(neg_doc_id)

                if not eligible_docs_all:
                    # Query has negatives, but none usable for this pair.
                    dropped_no_eligible_negative_for_pair += 1
                    continue

                if eligible_docs_unused:
                    neg_doc_id = eligible_docs_unused[0]
                    neg_recycled = False
                else:
                    key = (query_id, field)
                    pointer = recycle_pointer_by_query_field[key]
                    neg_doc_id = eligible_docs_all[pointer % len(eligible_docs_all)]
                    recycle_pointer_by_query_field[key] = pointer + 1
                    neg_recycled = True
                    recycled_negatives += 1

                product = products.get(neg_doc_id)
                if product is None:
                    dropped_missing_negative_product += 1
                    continue

                negative_text = get_negative_text(field, product)
                if not is_valid_text(
                    field,
                    negative_text,
                    args.min_title_chars,
                    args.min_description_chars,
                ):
                    dropped_invalid_negative_text += 1
                    continue

                used_negative_docs_by_query[query_id].add(neg_doc_id)

                triplet = {
                    "anchor": pair["anchor"],
                    "positive": pair["positive"],
                    "negative": negative_text,
                }
                out_f.write(json.dumps(triplet, ensure_ascii=False) + "\n")

                meta_writer.writerow(
                    {
                        "query_id": query_id,
                        "pos_document_id": pos_document_id,
                        "neg_document_id": neg_doc_id,
                        "field": field,
                        "neg_recycled": str(neg_recycled).lower(),
                        "anchor_chars": len(pair["anchor"]),
                        "positive_chars": len(pair["positive"]),
                        "negative_chars": len(negative_text),
                    }
                )
                emitted_triplets += 1

    queries_total = len(by_query_indices)
    queries_with_negatives = sum(1 for q in by_query_indices if q in negatives_by_query)
    dropped_total = (
        dropped_no_negative_docs_for_query
        + dropped_no_eligible_negative_for_pair
        + dropped_unknown_field
        + dropped_missing_negative_product
        + dropped_invalid_negative_text
    )

    print(f"Input pairs: {total_pairs}")
    print(f"Queries in pairs: {queries_total}")
    print(f"Queries with at least one negative doc id: {queries_with_negatives}")
    print(f"Triplets emitted: {emitted_triplets}")
    print(f"Negatives recycled: {recycled_negatives}")
    print(f"Dropped total: {dropped_total}")
    print(f"Dropped no negative docs for query: {dropped_no_negative_docs_for_query}")
    print(f"Dropped no eligible negative for pair: {dropped_no_eligible_negative_for_pair}")
    print(f"Dropped unknown field: {dropped_unknown_field}")
    print(f"Dropped missing negative product: {dropped_missing_negative_product}")
    print(f"Dropped invalid negative text: {dropped_invalid_negative_text}")
    print(f"Output triplets: {output_path}")
    print(f"Output metadata: {metadata_output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
