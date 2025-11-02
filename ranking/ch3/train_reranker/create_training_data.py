#!/usr/bin/env python3
import argparse
import csv
import os
from pathlib import Path
from vespa.application import Vespa
from dotenv import load_dotenv

# Load environment variables from ch2/evaluation/.env
script_dir = Path(__file__).parent
env_path = script_dir / '../../ch2/evaluation/.env'
load_dotenv(dotenv_path=env_path)

VESPA_ENDPOINT = os.getenv('VESPA_ENDPOINT')
VESPA_CERT_PATH = os.getenv('VESPA_CERT_PATH')
VESPA_KEY_PATH = os.getenv('VESPA_KEY_PATH')

# Initialize Vespa app
vespa_app = Vespa(url=VESPA_ENDPOINT, cert=VESPA_CERT_PATH, key=VESPA_KEY_PATH)

def load_queries(queries_file):
    """Load query_id -> query_text mapping from CSV"""
    queries = {}
    with open(queries_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries[row['query_id']] = row['query_text']
    return queries

def load_judgements(judgements_file):
    """Load judgements grouped by query_id"""
    judgements = {}
    with open(judgements_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            query_id = row['query_id']
            doc_id = row['document_id']
            rating = row['rating']
            
            if query_id not in judgements:
                judgements[query_id] = {}
            judgements[query_id][doc_id] = rating
    return judgements

def query_vespa(query_text):
    """Query Vespa and return results"""
    query_body = {
        "yql": '''
            select * from product where ({targetHits:100}nearestNeighbor(ProductName_embedding,q_embedding)) OR ({targetHits:100}nearestNeighbor(Description_embedding,q_embedding)) OR
              userQuery()
            ''',
        "query": query_text,
        "input.query(q_embedding)": "embed(@query)",
        "ranking.profile": "debug"
    }
    
    with vespa_app.syncio(connections=1) as session:
        response = session.query(body=query_body, hits=100)
    
    return response.get_json()

def extract_features(hit):
    """Extract features from a Vespa hit"""
    fields = hit['fields']
    summary = fields['summaryfeatures']
    
    return {
        'relevance_score': hit['relevance'],
        'Price': fields['Price'],
        'AverageRating': float(fields['AverageRating']),
        'closeness_description': summary['closeness_description'],
        'closeness_productname': summary['closeness_productname'],
        'native_rank_description': summary['native_rank_description'],
        'native_rank_name': summary['native_rank_name']
    }

def main(queries_file, judgements_file, output_file):
    # Load data
    print(f"Loading queries from {queries_file}...")
    queries = load_queries(queries_file)
    print(f"Loading judgements from {judgements_file}...")
    judgements = load_judgements(judgements_file)
    
    # Prepare output CSV
    fieldnames = [
        'query_id', 'doc_id', 'relevance_label', 'relevance_score',
        'Price', 'AverageRating', 'closeness_description', 'closeness_productname',
        'native_rank_description', 'native_rank_name'
    ]
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Process each query
        for query_id, query_text in queries.items():
            print(f"Processing query {query_id}: {query_text}")
            
            # Get judgements for this query
            query_judgements = judgements.get(query_id, {})
            if not query_judgements:
                print(f"  No judgements found for query {query_id}, skipping")
                continue
            
            # Query Vespa
            response = query_vespa(query_text)
            
            # Process results
            hits = response['root'].get('children', [])
            matched_count = 0
            
            for hit in hits:
                doc_id = hit['fields']['ProductID']
                
                # Check if this doc has a judgement
                if doc_id in query_judgements:
                    features = extract_features(hit)
                    
                    row = {
                        'query_id': query_id,
                        'doc_id': doc_id,
                        'relevance_label': query_judgements[doc_id],
                        **features
                    }
                    
                    writer.writerow(row)
                    matched_count += 1
            
            print(f"  Matched {matched_count}/{len(query_judgements)} judged documents")
    
    print(f"\nTraining data written to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create training/validation data CSV from queries and judgements by querying Vespa."
    )
    parser.add_argument(
        "--queries",
        type=str,
        default="train_queries.csv",
        help="Path to queries CSV file (default: train_queries.csv)"
    )
    parser.add_argument(
        "--judgements",
        type=str,
        default="train_judgements.csv",
        help="Path to judgements CSV file (default: train_judgements.csv)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="training_data.csv",
        help="Path to output CSV file (default: training_data.csv)"
    )
    
    args = parser.parse_args()
    main(args.queries, args.judgements, args.output)
