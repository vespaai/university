import json
import random
import re
import math

def clean_key(text):
    """Remove non-letter characters from text"""
    return re.sub(r'[^a-zA-Z]', '', str(text))

def create_sparse_tensor(product):
    """Create sparse tensor from Brand, Gender, PrimaryColor fields and PriceFactor"""
    sparse_tensor = {}
    fields = product.get('fields', {})
    
    # Process categorical fields
    categorical_fields = ['ProductBrand', 'Gender', 'PrimaryColor']
    for field_name in categorical_fields:
        field_value = fields.get(field_name)
        if field_value:
            key = f"{field_name}{clean_key(field_value)}"
            sparse_tensor[key] = 1
    
    # Add PriceFactor as (5 - log(Price))
    price = int(fields.get('Price'))
    if price and price > 0:
        sparse_tensor['PriceFactor'] = round(5 - math.log10(price), 2)
    
    return sparse_tensor

def add_rating_field(input_file, output_file):
    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        for line in infile:
            product = json.loads(line.strip())
            product['fields']['AverageRating'] = round(random.uniform(1, 5), 1)
            product['fields']['ProductFeatures'] = create_sparse_tensor(product)
            outfile.write(json.dumps(product) + '\n')

if __name__ == "__main__":
    add_rating_field('products.jsonl', 'products.jsonl')