import json
from vespa.application import Vespa
from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables from local .env file
script_dir = Path(__file__).parent
env_path = script_dir / '.env'
load_dotenv(dotenv_path=env_path)

VESPA_ENDPOINT = os.getenv('VESPA_ENDPOINT')
VESPA_CERT_PATH = os.getenv('VESPA_CERT_PATH')
VESPA_KEY_PATH = os.getenv('VESPA_KEY_PATH')


# we do embeddings on the fly on the initial feed
# and we don't want to overload Vespa
MAX_WORKERS=2
MAX_QUEUE_SIZE=100
MAX_CONNECTIONS=2

# Initialize Vespa app
vespa_app = Vespa(url=VESPA_ENDPOINT, cert=VESPA_CERT_PATH, key=VESPA_KEY_PATH)

# read articles.json
with open("articles.json", "r") as f:
    articles = json.load(f)

# make it Vespa format
all_docs = []
for article_title, content_list in articles.items():
    all_docs.append({
        'id': article_title,
        'fields': {
            'article_title_s': article_title,
            'chunk_ts': content_list
        }
    })

# load articles into Vespa
article_count = [0]  # Use list to allow modification in nested function
total_articles = len(all_docs)

def callback(response, id):
    article_count[0] += 1
    if article_count[0] % 10 == 0 or article_count[0] == total_articles:
        print(f"\rProgress: {article_count[0]}/{total_articles} articles processed", end='', flush=True)
        if article_count[0] == total_articles:
            print()  # New line when complete
    if response.status_code != 200:
        print(f"\nError for id {id}. Status code: {response.status_code}. Error: {response.get_json()}")

print(f"Feeding {total_articles} articles...")
vespa_app.feed_async_iterable(all_docs,
                              schema="article", 
                              namespace="wiki", 
                              callback=callback, 
                              max_workers=MAX_WORKERS,
                              max_queue_size=MAX_QUEUE_SIZE,
                              max_connections=MAX_CONNECTIONS,
                              operation_type="feed")
print("\nArticles feeding completed")

# Function to read metadata and yield update operations
def read_metadata_updates(metadata_file, limit=None):
    """
    Read metadata.ndjson line by line and yield update operations.
    
    Args:
        metadata_file: Path to the metadata.ndjson file
        limit: Maximum number of lines to read (None for all)
    """
    field_mapping = {
        'characters': 'characters_i',
        'words': 'words_i',
        'sections': 'sections_i',
        'unique_references': 'unique_references_i',
        'watchers': 'watchers_i',
        'revisions': 'revisions_i',
        'editors': 'editors_i',
        'created_at': 'created_at_s',
        'modified_at': 'modified_at_s',
        'links_ext_count': 'links_ext_count_i',
        'links_out_count': 'links_out_count_i',
        'links_in_count': 'links_in_count_i',
        'redirects_count': 'redirects_count_i'
    }
    
    with open(metadata_file, "r") as f:
        for line_num, line in enumerate(f, 1):
            if limit and line_num > limit:
                break
            
            # Parse JSON line
            metadata = json.loads(line.strip())
            
            # Get article ID (this maps to article_title_s in Vespa)
            article_id = metadata.get('article')
            if not article_id:
                continue
            
            # Build fields dictionary with assign operations
            fields = {}
            for metadata_key, vespa_field in field_mapping.items():
                if metadata_key in metadata:
                    fields[vespa_field] = metadata[metadata_key] # {"assign": metadata[metadata_key]}
            
            # Yield update operation
            yield {
                'id': article_id,
                'fields': fields
            }

# Update documents with metadata
print("Updating documents with metadata...")
metadata_count = [0]  # Use list to allow modification in nested function

def metadata_callback(response, id):
    metadata_count[0] += 1
    if metadata_count[0] % 100 == 0:
        print(f"\rProgress: {metadata_count[0]} metadata updates processed", end='', flush=True)
    if response.status_code != 200:
        print(f"\nError for id {id}. Status code: {response.status_code}. Error: {response.get_json()}")

metadata_updates = read_metadata_updates("metadata.ndjson", limit=None)
# updates don't need to re-compute embeddings
# we can use the default max_workers & other settings for more throughput
vespa_app.feed_async_iterable(
    metadata_updates, 
    schema="article", 
    namespace="wiki", 
    callback=metadata_callback,
    operation_type="update"
)
print(f"\nMetadata updates completed: {metadata_count[0]} documents updated")

