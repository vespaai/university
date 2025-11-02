# NOTE: this is a PoC. The prompt can be improved, e.g. with some examples.
# More details at https://blog.vespa.ai/improving-retrieval-with-llm-as-a-judge/

# MULTI_RETREIVAL SUPPORT:
# This script supports combining multiple query functions (e.g., vector + lexical search).
# Configure QUERY_FUNCTIONS below to use single or multiple search strategies.
# Results are automatically concatenated and deduplicated by document ID.

import csv
import json
import requests
import os
from pathlib import Path
from openai import OpenAI
import traceback
import evaluate

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Note: python-dotenv not installed. Install with 'pip install python-dotenv' to use .env files.")

########################################################
######## CONFIGURATION BEGIN ############################
########################################################

# Configuration from environment variables with fallback defaults
VESPA_ENDPOINT = os.getenv('VESPA_ENDPOINT', 'http://localhost:8080')
# Ensure endpoint has /search/ suffix
if not VESPA_ENDPOINT.endswith('/search/'):
    VESPA_ENDPOINT = VESPA_ENDPOINT.rstrip('/') + '/search/'

VESPA_CERT_PATH = os.getenv('VESPA_CERT_PATH', '')
VESPA_KEY_PATH = os.getenv('VESPA_KEY_PATH', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Optional configuration
HITS = int(os.getenv('HITS', '100'))  # number of documents to return from Vespa and evaluate
QUERIES_FILE = os.getenv('QUERIES_FILE', 'queries.csv')
JUDGEMENTS_FILE = os.getenv('JUDGEMENTS_FILE', 'judgements.csv')

# Validate certificate paths
MTLS_CERT_PATH = None
MTLS_KEY_PATH = None

if VESPA_CERT_PATH and VESPA_KEY_PATH:
    cert_path = Path(VESPA_CERT_PATH)
    key_path = Path(VESPA_KEY_PATH)
    
    if cert_path.exists() and key_path.exists():
        MTLS_CERT_PATH = str(cert_path)
        MTLS_KEY_PATH = str(key_path)
        print(f"Using mTLS with cert: {cert_path}")
    else:
        print(f"Warning: Certificate or key file not found. Connecting without mTLS.")
        if not cert_path.exists():
            print(f"  Cert not found: {cert_path}")
        if not key_path.exists():
            print(f"  Key not found: {key_path}")
else:
    print(f"Connecting to Vespa without mTLS (no cert/key configured)")

print(f"Vespa endpoint: {VESPA_ENDPOINT}")
print(f"Will request {HITS} hits per query function")

# Query functions to use from evaluate.py
# Use an array to combine multiple search strategies and 
# Results will be concatenated and deduplicated by document ID get multiple perspectives
QUERY_FUNCTIONS = [evaluate.vector_search, evaluate.lexical_search]
# QUERY_FUNCTIONS = [evaluate.vector_search]  # Single function
# QUERY_FUNCTIONS = [evaluate.lexical_search]  # Single function

print(f"Using {len(QUERY_FUNCTIONS)} query function(s): {[f.__name__ for f in QUERY_FUNCTIONS]}")
print(f"Max documents to evaluate per query: {HITS * len(QUERY_FUNCTIONS)} (before deduplication)")

########################################################
######## CONFIGURATION END ##############################
########################################################

def load_queries():
    """Load queries from CSV file."""
    queries = []
    with open(QUERIES_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries.append({
                'query_id': row['query_id'],
                'query_text': row['query_text']
            })
    return queries

def load_existing_judgements_rows():
    """Load existing judgements and return a list of all row dictionaries."""
    existing_rows = []
    
    if not os.path.exists(JUDGEMENTS_FILE):
        return existing_rows
    
    try:
        with open(JUDGEMENTS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip empty rows
                if row.get('query_id') and row.get('document_id'):
                    existing_rows.append(row)
    except Exception as e:
        print(f"Error loading existing judgements: {e}")
    
    return existing_rows

def load_existing_judgements():
    """Load existing judgements and return a set of (query_id, document_id) pairs."""
    existing_rows = load_existing_judgements_rows()
    return {(row['query_id'], row['document_id']) for row in existing_rows}

def execute_vespa_query(query_text):
    """Execute multiple queries against Vespa, concatenate and deduplicate results."""
    headers = {
        'Content-Type': 'application/json'
    }

    # Configure mTLS if certificates are provided
    cert = None
    if MTLS_CERT_PATH and MTLS_KEY_PATH:
        cert = (MTLS_CERT_PATH, MTLS_KEY_PATH)

    all_documents = []
    seen_doc_ids = set()
    total_before_dedup = 0

    # Execute each query function
    for query_func in QUERY_FUNCTIONS:
        payload = query_func(query_text, HITS)
        
        response = requests.post(VESPA_ENDPOINT, headers=headers, json=payload, cert=cert)
        response.raise_for_status()
        
        result = response.json()
        documents = result.get('root', {}).get('children', [])
        total_before_dedup += len(documents)
        
        # Add documents, deduplicating by ProductID
        added_count = 0
        for doc in documents:
            fields = doc.get('fields', {})
            doc_id = fields.get('ProductID')
            
            if doc_id and doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                all_documents.append(doc)
                added_count += 1
        
        duplicate_count = len(documents) - added_count
        if len(QUERY_FUNCTIONS) > 1:
            print(f"  {query_func.__name__}: {len(documents)} documents ({added_count} new, {duplicate_count} duplicates)")
    
    # Show deduplication summary
    if len(QUERY_FUNCTIONS) > 1:
        print(f"  Combined: {len(all_documents)} unique documents (from {total_before_dedup} total)")
    
    # Return in the same format as original response
    return {
        'root': {
            'children': all_documents
        }
    }

def get_openai_judgements(query_text, documents):
    """Get relevance judgements from OpenAI for query-document pairs using micro-batches."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    total_docs = len(documents)
    if total_docs == 0:
        return []

    batch_size = 10
    num_batches = (total_docs + batch_size - 1) // batch_size
    judgements = []

    for batch_index in range(num_batches):
        start_idx = batch_index * batch_size
        end_idx = min(start_idx + batch_size, total_docs)
        batch_docs = documents[start_idx:end_idx]

        # Build JSON array of products including available fields
        products = []
        for doc in batch_docs:
            product: dict = {}
            if doc.get('ProductID') is not None:
                product['ProductID'] = str(doc.get('ProductID'))
            if doc.get('ProductName') is not None:
                product['ProductName'] = doc.get('ProductName')
            if doc.get('ProductBrand') is not None:
                product['ProductBrand'] = doc.get('ProductBrand')
            if doc.get('Gender') is not None:
                product['Gender'] = doc.get('Gender')
            if doc.get('Price') is not None:
                product['Price'] = doc.get('Price')
            if doc.get('Description') is not None:
                product['Description'] = doc.get('Description')
            if doc.get('PrimaryColor') is not None:
                product['PrimaryColor'] = doc.get('PrimaryColor')
            if doc.get('AverageRating') is not None:
                product['AverageRating'] = doc.get('AverageRating')
            products.append(product)

        products_json = json.dumps(products, ensure_ascii=False)

        prompt = f"""
Please rate the relevance of each of the following products to the search query on a scale of 0-3.

Query: "{query_text}"

Products (JSON array):
{products_json}

Rating scale:
- 3: Excellent match - directly answers the query
- 2: Good match - relevant and useful
- 1: Possible match - could be relevant for some users
- 0: Irrelevant - does not answer the query

Respond with exactly a JSON array of objects. Each object must have:
- "ProductID": string
- "rating": number (0, 1, 2, or 3)

Example:
[{{"ProductID":"123","rating":2}},{{"ProductID":"456","rating":0}}]
"""

        # Show batch progress
        print(f"\rEvaluating batch {batch_index + 1}/{num_batches} ({len(batch_docs)} docs)...", end='', flush=True)

        try:
            response = client.responses.create(
                model="gpt-5-mini",
                input=prompt
            )

            response_text = response.output_text.strip()
            parsed = json.loads(response_text)
            if not isinstance(parsed, list):
                raise ValueError("Response is not a JSON array")

            # Map ratings by ProductID (string)
            ratings_by_id: dict = {}
            for item in parsed:
                product_id_value = item.get('ProductID')
                rating_value = item.get('rating')
                if product_id_value is None:
                    continue
                product_id_str = str(product_id_value)
                rating_int = int(rating_value)
                if rating_int not in [0, 1, 2, 3]:
                    raise ValueError(f"Invalid rating: {rating_int}")
                ratings_by_id[product_id_str] = rating_int

            # Smoke test: ensure same count
            if len(parsed) != len(batch_docs):
                raise ValueError(f"Expected {len(batch_docs)} ratings, got {len(parsed)}. Missing IDs will default to 0.")

        except Exception as e:
            print(f"\nError getting batch ratings: {e}")
            continue

        # Build judgements for this batch
        for doc in batch_docs:
            doc_id = doc.get('ProductID')
            rating = ratings_by_id.get(doc_id)
            judgements.append({
                'query_id': None,  # Will be set by caller
                'document_id': doc_id,
                'rating': rating
            })

    print(f"\rCompleted evaluation of {total_docs} documents in {num_batches} batches.")
    return judgements

def save_judgements(new_judgements):
    """Save judgements to CSV file, appending new ones to existing."""
    # Load all existing judgements using the reusable function
    all_judgements = load_existing_judgements_rows()
    
    # Add new judgements
    all_judgements.extend(new_judgements)
    
    # Write all judgements back to file
    with open(JUDGEMENTS_FILE, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['query_id', 'document_id', 'rating']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_judgements)

def main():
    """Main function to process all queries and generate judgements."""
    print("Loading queries...")
    queries = load_queries()
    
    print("Loading existing judgements...")
    existing_judgements = load_existing_judgements()
    print(f"Found {len(existing_judgements)} existing judgements")

    all_new_judgements = []

    for i, query in enumerate(queries, 1):
        print(f"Processing query {i}/{len(queries)}: {query['query_text']}")

        try:
            # Execute Vespa query
            results = execute_vespa_query(query['query_text'])

            # Extract documents from results
            documents = results.get('root', {}).get('children', [])
            doc_fields = [doc.get('fields', {}) for doc in documents]

            if not doc_fields:
                print(f"No results for query: {query['query_text']}")
                continue

            # Filter out documents that already have judgements
            new_doc_fields = []
            for doc in doc_fields:
                doc_id = doc.get('ProductID', '')
                pair = (query['query_id'], doc_id)
                if pair not in existing_judgements:
                    new_doc_fields.append(doc)
                else:
                    print(f"Skipping document {doc_id} for query {query['query_id']} - already evaluated")
            
            if not new_doc_fields:
                print(f"No new documents to evaluate for query: {query['query_text']} - skipping")
                continue
            
            print(f"Evaluating {len(new_doc_fields)} new documents (out of {len(doc_fields)} total)")

            # Get OpenAI judgements for new documents only
            judgements = get_openai_judgements(query['query_text'], new_doc_fields)

            # Set query_id for all judgements
            for judgement in judgements:
                judgement['query_id'] = query['query_id']

            # Save judgements immediately after each query to avoid losing work
            if judgements:
                print(f"Saving {len(judgements)} new judgements for query {query['query_id']}...")
                save_judgements(judgements)
                print(f"Saved! Judgements appended to {JUDGEMENTS_FILE}")
            
            # Add new judgements to existing set to avoid duplicates in subsequent queries
            for judgement in judgements:
                existing_judgements.add((judgement['query_id'], judgement['document_id']))

        except Exception as e:
            print(f"Error processing query {query['query_id']}")
            traceback.print_exc()
            continue
    
        # # stop after N queries
        # if i > 10:
        #     break

    print("Processing complete!")

if __name__ == "__main__":
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY is required but not set.")
        print("Please set it via:")
        print("  1. Environment variable: export OPENAI_API_KEY='your-key'")
        print("  2. .env file: OPENAI_API_KEY=your-key")
        print("\nAsk your instructor if you don't have an OpenAI API key.")
        exit(1)
    main()