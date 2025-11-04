#!/usr/bin/env python3
"""
Split queries and judgements into training and test sets.
Split ratio: 80% train, 20% test
"""

import csv
import os
import random
from pathlib import Path

# Configuration
TRAIN_RATIO = 0.8
TEST_RATIO = 0.2
SPLIT_SEED_ENV = os.getenv("SPLIT_SEED") or os.getenv("SEED")
RNG = random.Random(int(SPLIT_SEED_ENV)) if SPLIT_SEED_ENV is not None else random.Random()

# Paths
SCRIPT_DIR = Path(__file__).parent
EVAL_DIR = SCRIPT_DIR.parent.parent / "ch2" / "evaluation"
QUERIES_FILE = EVAL_DIR / "queries.csv"
JUDGEMENTS_FILE = EVAL_DIR / "judgements.csv"

# Output files
OUTPUT_DIR = SCRIPT_DIR
TRAIN_QUERIES = OUTPUT_DIR / "train_queries.csv"
TEST_QUERIES = OUTPUT_DIR / "test_queries.csv"
TRAIN_JUDGEMENTS = OUTPUT_DIR / "train_judgements.csv"
TEST_JUDGEMENTS = OUTPUT_DIR / "test_judgements.csv"


def load_queries():
    """Load all queries from the queries CSV file."""
    queries = []
    with open(QUERIES_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries.append(row)
    return queries


def split_queries(queries):
    """Split queries into train and test sets using a random shuffle."""
    total = len(queries)
    train_size = int(total * TRAIN_RATIO)

    shuffled = list(queries)
    RNG.shuffle(shuffled)

    train_queries = shuffled[:train_size]
    test_queries = shuffled[train_size:]

    return train_queries, test_queries


def write_queries(queries, output_file):
    """Write queries to a CSV file."""
    if not queries:
        print(f"Warning: No queries to write to {output_file}")
        return
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['query_id', 'query_text'])
        writer.writeheader()
        writer.writerows(queries)
    
    print(f"Wrote {len(queries)} queries to {output_file}")


def get_query_ids(queries):
    """Extract query_id set from queries."""
    return set(q['query_id'] for q in queries)


def split_judgements(train_ids, test_ids):
    """Split judgements based on query_id sets."""
    train_judgements = []
    test_judgements = []
    
    with open(JUDGEMENTS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            query_id = row['query_id']
            if query_id in train_ids:
                train_judgements.append(row)
            elif query_id in test_ids:
                test_judgements.append(row)
    
    return train_judgements, test_judgements


def write_judgements(judgements, output_file):
    """Write judgements to a CSV file."""
    if not judgements:
        print(f"Warning: No judgements to write to {output_file}")
        return
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['query_id', 'document_id', 'rating'])
        writer.writeheader()
        writer.writerows(judgements)
    
    print(f"Wrote {len(judgements)} judgements to {output_file}")


def main():
    print("=" * 60)
    print("Splitting queries and judgements into train/test sets")
    print(f"Split ratio: {int(TRAIN_RATIO*100)}% train, {int(TEST_RATIO*100)}% test")
    print("=" * 60)
    if SPLIT_SEED_ENV is not None:
        print(f"Using random seed: {int(SPLIT_SEED_ENV)}")
    
    # Load and split queries
    print(f"\nLoading queries from: {QUERIES_FILE}")
    queries = load_queries()
    print(f"Total queries: {len(queries)}")
    
    train_queries, test_queries = split_queries(queries)
    print(f"\nQuery split:")
    print(f"  Train: {len(train_queries)} queries")
    print(f"  Test:  {len(test_queries)} queries")
    
    # Write query splits
    print(f"\nWriting query splits to: {OUTPUT_DIR}")
    write_queries(train_queries, TRAIN_QUERIES)
    write_queries(test_queries, TEST_QUERIES)
    
    # Get query ID sets
    train_ids = get_query_ids(train_queries)
    test_ids = get_query_ids(test_queries)
    
    # Split judgements
    print(f"\nLoading and splitting judgements from: {JUDGEMENTS_FILE}")
    train_judgements, test_judgements = split_judgements(train_ids, test_ids)
    
    print(f"\nJudgement split:")
    print(f"  Train: {len(train_judgements)} judgements")
    print(f"  Test:  {len(test_judgements)} judgements")
    print(f"  Total: {len(train_judgements) + len(test_judgements)} judgements")
    
    # Write judgement splits
    print(f"\nWriting judgement splits to: {OUTPUT_DIR}")
    write_judgements(train_judgements, TRAIN_JUDGEMENTS)
    write_judgements(test_judgements, TEST_JUDGEMENTS)
    
    print("\n" + "=" * 60)
    print("Split complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

