from vespa.application import Vespa
from vespa.evaluation import VespaEvaluator
import csv
import os
from pathlib import Path

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
VESPA_CERT_PATH = os.getenv('VESPA_CERT_PATH', '')
VESPA_KEY_PATH = os.getenv('VESPA_KEY_PATH', '')

# Build Vespa connection parameters
vespa_kwargs = {'url': VESPA_ENDPOINT}

# Only add cert/key if both are provided and files exist
if VESPA_CERT_PATH and VESPA_KEY_PATH:
    cert_path = Path(VESPA_CERT_PATH)
    key_path = Path(VESPA_KEY_PATH)
    
    if cert_path.exists() and key_path.exists():
        vespa_kwargs['cert'] = str(cert_path)
        vespa_kwargs['key'] = str(key_path)
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

vespa_app = Vespa(**vespa_kwargs)

FIELDS_TO_RETURN = os.getenv('FIELDS_TO_RETURN', 'ProductID,ProductName,ProductBrand,Gender,Price,Description,PrimaryColor,AverageRating')

def vector_search(query_text: str, top_k: int) -> dict:
    # targetHits should be higher than the number of hits to return, for accuracy
    target_hits = top_k * 10

    return {
        "yql": f"select {FIELDS_TO_RETURN} from product where ({{targetHits:{target_hits}}}nearestNeighbor(ProductName_embedding,q_embedding)) OR ({{targetHits:{target_hits}}}nearestNeighbor(Description_embedding,q_embedding))",
        # make sure this matches the vector search rank profile in the schema
        "ranking.profile": "closeness_productname_description",
        "approximate_query_string": query_text,
        "input.query(q_embedding)": "embed(@approximate_query_string)",
        "hits": top_k
    }
    
def lexical_search(query_text: str, top_k: int) -> dict:
    return {
        "yql": f"select {FIELDS_TO_RETURN} from sources * where userInput('{query_text}');",
        "hits": top_k,
        # make sure this matches the lexical search rank profile in the schema
        "ranking.profile": "default",
    }

def hybrid_search(query_text: str, top_k: int) -> dict:
    target_hits = top_k * 10
    return {
        "yql": '''
            select * from product where ({targetHits:100}nearestNeighbor(ProductName_embedding,q_embedding))
             OR ({targetHits:100}nearestNeighbor(Description_embedding,q_embedding)) 
             OR userQuery()
            ''',
        "query": query_text,
        "input.query(q_embedding)": "embed(@query)",
        "ranking.profile": "hybrid"
    }

QUERY_FUNCTION = lexical_search
# QUERY_FUNCTION = vector_search
# QUERY_FUNCTION = hybrid_search

########################################################
######## CONFIGURATION END ##############################
########################################################

if __name__ == "__main__":
    # Load queries from CSV file
    queries = {}
    with open('queries.csv', 'r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            queries[row['query_id']] = row['query_text']

    print("Loaded queries (first 5):")
    for i, (query_id, query_text) in enumerate(queries.items()):
        if i >= 5:
            break
        print(f'"{query_id}": "{query_text}"')

    # Load judgements from CSV file
    relevant_docs = {}
    with open('judgements.csv', 'r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            query_id = row['query_id']
            document_id = row['document_id']
            rating = int(row['rating'])
            
            if query_id not in relevant_docs:
                relevant_docs[query_id] = {}
            
            # Only include documents with rating > 0 and normalize rating (Evaluator expects a value between 0 and 1)
            if rating > 0:
                normalized_rating = rating / 3.0
                relevant_docs[query_id][document_id] = normalized_rating

    print(f"\nLoaded judgements for {len(relevant_docs)} queries")
    print("Sample judgements (first 3 queries):")
    for i, (query_id, docs) in enumerate(relevant_docs.items()):
        if i >= 3:
            break
        print(f'Query {query_id}: {len(docs)} relevant documents')
        # Show first 3 documents for this query
        sample_docs = dict(list(docs.items())[:3])
        print(f'  Sample: {sample_docs}')

    print("================================================")
    print(f"Evaluating {len(relevant_docs)} queries using query function: {QUERY_FUNCTION.__name__}")
    print("================================================")
    evaluator = VespaEvaluator(
        # list of queries (ID, query text)
        queries=queries,
        # list of judgements (query ID, document ID, rating)
        relevant_docs=relevant_docs,
        # how to query Vespa
        vespa_query_fn=QUERY_FUNCTION,
        id_field="ProductID",
        # how to connect to Vespa (application)
        app=vespa_app
    )

    results = evaluator()
    print("Primary metric:", evaluator.primary_metric)
    print("All results:", results)

    # DEBUG: test query
    # import json
    # with vespa_app.syncio(connections=1) as session:
    #     response = session.query(yql="select * from product where true")
    # print(json.dumps(response.get_json(), indent=2))

