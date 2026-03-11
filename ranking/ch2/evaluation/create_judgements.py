# NOTE: this is a PoC. The prompt can be improved, e.g. with some examples.
# More details at https://blog.vespa.ai/improving-retrieval-with-llm-as-a-judge/

# MULTI_RETREIVAL SUPPORT:
# This script supports combining multiple query functions (e.g., vector + lexical search).
# Configure QUERY_FUNCTIONS below to use single or multiple search strategies.
# Results are automatically concatenated and deduplicated by document ID.

import csv
import json
import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import openai
import requests
from openai import OpenAI

import evaluate

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Note: python-dotenv not installed. Install with 'pip install python-dotenv' to use .env files.")

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

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
NUM_THREADS = int(os.getenv('NUM_THREADS', '8'))

# Validate certificate paths
MTLS_CERT_PATH = None
MTLS_KEY_PATH = None

if VESPA_CERT_PATH and VESPA_KEY_PATH:
    cert_path = Path(VESPA_CERT_PATH)
    key_path = Path(VESPA_KEY_PATH)
    
    if cert_path.exists() and key_path.exists():
        MTLS_CERT_PATH = str(cert_path)
        MTLS_KEY_PATH = str(key_path)
        logger.info("Using mTLS with cert: %s", cert_path)
    else:
        logger.warning("Certificate or key file not found. Connecting without mTLS.")
        if not cert_path.exists():
            logger.warning("  Cert not found: %s", cert_path)
        if not key_path.exists():
            logger.warning("  Key not found: %s", key_path)
else:
    logger.info("Connecting to Vespa without mTLS (no cert/key configured)")

logger.info("Vespa endpoint: %s", VESPA_ENDPOINT)
logger.info("Will request %d hits per query function", HITS)

# Query functions to use from evaluate.py
# Use an array to combine multiple search strategies and 
# Results will be concatenated and deduplicated by document ID get multiple perspectives
QUERY_FUNCTIONS = [evaluate.vector_search, evaluate.lexical_search]
# QUERY_FUNCTIONS = [evaluate.vector_search]  # Single function
# QUERY_FUNCTIONS = [evaluate.lexical_search]  # Single function

logger.info("Using %d query function(s): %s", len(QUERY_FUNCTIONS), [f.__name__ for f in QUERY_FUNCTIONS])
logger.info("Max documents to evaluate per query: %d (before deduplication)", HITS * len(QUERY_FUNCTIONS))
logger.info("Using %d threads", NUM_THREADS)

# OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

########################################################
######## CONFIGURATION END ##############################
########################################################

_thread_local = threading.local()

def _get_session():
    """Return a per-thread requests.Session, recreating it on connection errors."""
    if not hasattr(_thread_local, 'session'):
        _thread_local.session = requests.Session()
    return _thread_local.session

def _reset_session():
    """Discard the current thread's session so the next call creates a fresh one."""
    _thread_local.session = requests.Session()

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
        logger.error("Error loading existing judgements: %s", e)
    
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
        
        try:
            response = _get_session().post(VESPA_ENDPOINT, headers=headers, json=payload, cert=cert)
        except requests.ConnectionError:
            logger.warning("Connection error to Vespa, retrying with fresh session...")
            _reset_session()
            response = _get_session().post(VESPA_ENDPOINT, headers=headers, json=payload, cert=cert)
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
            logger.info("  %s: %d documents (%d new, %d duplicates)",
                        query_func.__name__, len(documents), added_count, duplicate_count)
    
    # Show deduplication summary
    if len(QUERY_FUNCTIONS) > 1:
        logger.info("  Combined: %d unique documents (from %d total)", len(all_documents), total_before_dedup)
    
    # Return in the same format as original response
    return {
        'root': {
            'children': all_documents
        }
    }

def call_openai_with_backoff(prompt, max_retries=7):
    """Call OpenAI API with exponential backoff on rate limit errors."""
    delay = 1.0
    for attempt in range(max_retries + 1):
        try:
            return openai_client.responses.create(
                model="gpt-5-mini",
                input=prompt
            )
        except openai.RateLimitError:
            if attempt == max_retries:
                raise
            sleep_time = delay * (2 ** attempt) * (1 + random.random())
            logger.warning("Rate limited (attempt %d/%d), retrying in %.1fs...",
                           attempt + 1, max_retries, sleep_time)
            time.sleep(sleep_time)

def get_openai_judgements(query_text, documents):
    """Get relevance judgements from OpenAI for query-document pairs using micro-batches."""
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

        logger.info("Evaluating batch %d/%d (%d docs)...", batch_index + 1, num_batches, len(batch_docs))

        try:
            response = call_openai_with_backoff(prompt)

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
            logger.error("Error getting batch ratings: %s", e)
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

    logger.info("Completed evaluation of %d documents in %d batches.", total_docs, num_batches)
    return judgements

def save_judgements(new_judgements, lock):
    """Append new judgements to CSV file (thread-safe)."""
    fieldnames = ['query_id', 'document_id', 'rating']
    with lock:
        file_exists = os.path.exists(JUDGEMENTS_FILE) and os.path.getsize(JUDGEMENTS_FILE) > 0
        with open(JUDGEMENTS_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(new_judgements)

def process_query(query, existing_judgements, judgements_lock):
    """Process a single query: search Vespa, filter, get OpenAI judgements, save."""
    query_id = query['query_id']
    query_text = query['query_text']

    # Execute Vespa query
    results = execute_vespa_query(query_text)

    # Extract documents from results
    documents = results.get('root', {}).get('children', [])
    doc_fields = [doc.get('fields', {}) for doc in documents]

    if not doc_fields:
        logger.info("No results for query: %s", query_text)
        return 0

    # Filter out documents that already have judgements
    new_doc_fields = []
    skipped_count = 0
    with judgements_lock:
        for doc in doc_fields:
            doc_id = doc.get('ProductID', '')
            pair = (query_id, doc_id)
            if pair not in existing_judgements:
                new_doc_fields.append(doc)
            else:
                logger.debug("Skipping document %s for query %s - already evaluated", doc_id, query_id)
                skipped_count += 1

    if skipped_count > 0:
        logger.info("Query %s: %d/%d docs already evaluated", query_id, skipped_count, len(doc_fields))

    if not new_doc_fields:
        logger.info("No new documents to evaluate for query: %s - skipping", query_text)
        return 0

    logger.info("Query %s: evaluating %d new documents (out of %d total)",
                query_id, len(new_doc_fields), len(doc_fields))

    # Get OpenAI judgements for new documents only
    judgements = get_openai_judgements(query_text, new_doc_fields)

    # Set query_id for all judgements
    for judgement in judgements:
        judgement['query_id'] = query_id

    # Save judgements immediately after each query to avoid losing work
    if judgements:
        logger.info("Saving %d new judgements for query %s...", len(judgements), query_id)
        save_judgements(judgements, judgements_lock)
        logger.info("Saved! Judgements appended to %s", JUDGEMENTS_FILE)

    # Add new judgements to existing set to avoid duplicates in subsequent queries
    with judgements_lock:
        for judgement in judgements:
            existing_judgements.add((judgement['query_id'], judgement['document_id']))

    return len(judgements)

def main():
    """Main function to process all queries and generate judgements."""
    logger.info("Loading queries...")
    queries = load_queries()
    
    logger.info("Loading existing judgements...")
    existing_judgements = load_existing_judgements()
    logger.info("Found %d existing judgements", len(existing_judgements))

    # To limit queries for testing, slice: queries[:10]
    judgements_lock = threading.Lock()
    total = len(queries)
    completed = 0

    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = {
            executor.submit(process_query, query, existing_judgements, judgements_lock): query
            for query in queries
        }
        for future in as_completed(futures):
            query = futures[future]
            try:
                future.result()
            except Exception:
                logger.error("Error processing query %s", query['query_id'], exc_info=True)
            completed += 1
            logger.info("Progress: %d/%d queries done", completed, total)

    logger.info("Processing complete!")

if __name__ == "__main__":
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is required but not set.")
        logger.error("Please set it via:")
        logger.error("  1. Environment variable: export OPENAI_API_KEY='your-key'")
        logger.error("  2. .env file: OPENAI_API_KEY=your-key")
        logger.error("Ask your instructor if you don't have an OpenAI API key.")
        exit(1)
    main()
