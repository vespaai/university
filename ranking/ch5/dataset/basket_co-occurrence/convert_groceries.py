#!/usr/bin/env python3
"""
Convert groceries.csv to groceries.jsonl for Vespa ingestion.

NOTE: groceries.csv is from https://www.kaggle.com/datasets/irfanasrullah/groceries
"""

import csv
import json
import uuid
from pathlib import Path

def convert_csv_to_jsonl(csv_path, jsonl_path):
    """
    Convert groceries.csv to groceries.jsonl format for Vespa.
    
    Args:
        csv_path: Path to input CSV file
        jsonl_path: Path to output JSONL file
    """
    csv_file = Path(csv_path)
    jsonl_file = Path(jsonl_path)
    
    with open(csv_file, 'r', encoding='utf-8') as infile, \
         open(jsonl_file, 'w', encoding='utf-8') as outfile:
        
        reader = csv.DictReader(infile)
        
        for row in reader:
            # Extract items from the row, skipping empty values
            items = []
            for key, value in row.items():
                # Skip the "Item(s)" column and empty values
                if key != "Item(s)" and value and value.strip():
                    items.append(value.strip())
            
            # Skip rows with no items
            if not items:
                continue
            
            # Generate UUID for this basket
            basket_id = str(uuid.uuid4())
            
            # Create the JSON object in the required format
            json_obj = {
                "put": f"id:ecommerce:basket::{basket_id}",
                "fields": {
                    "items": items
                }
            }
            
            # Write as a single line to the JSONL file
            outfile.write(json.dumps(json_obj) + '\n')

if __name__ == "__main__":
    # Get the directory of this script
    script_dir = Path(__file__).parent
    
    csv_path = script_dir / "groceries.csv"
    jsonl_path = script_dir / "groceries.jsonl"
    
    print(f"Converting {csv_path} to {jsonl_path}...")
    convert_csv_to_jsonl(csv_path, jsonl_path)
    print(f"Conversion complete! Output written to {jsonl_path}")
