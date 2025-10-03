from vespa.application import Vespa
from vespa.evaluation import VespaEvaluator
import csv

# NOTE: make sure you do `source prepare_env.sh` before running this script

### CONFIGURATION

#RANKING_PROFILE = "closeness_productname_description"
RANKING_PROFILE = "default"
vespa_app = Vespa(url="<mTLS_ENDPOINT_DNS_GOES_HERE>",
    cert='/Users/student/.vespa/<YOUR_TENANT>.<YOUR_APPLICATION>.default/data-plane-public-cert.pem',
    key='/Users/student/.vespa/<YOUR_TENANT>.<YOUR_APPLICATION>.default/data-plane-private-key.pem')


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

# how to query Vespa
def my_vespa_query_fn(query_text: str, top_k: int) -> dict:
    return {
        "yql": 'select * from sources * where userInput("' + query_text + '");',
        "hits": top_k,
        "ranking": RANKING_PROFILE,
    }

evaluator = VespaEvaluator(
    queries=queries,
    relevant_docs=relevant_docs,
    vespa_query_fn=my_vespa_query_fn,
    app=vespa_app,
    name="test-run"
)

results = evaluator()
print("Primary metric:", evaluator.primary_metric)
print("All results:", results)

# DEBUG: test query
# import json
# with vespa_app.syncio(connections=1) as session:
#     response = session.query(yql="select * from product where true")
# print(json.dumps(response.get_json(), indent=2))

