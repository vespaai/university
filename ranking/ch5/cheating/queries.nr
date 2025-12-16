#%%vespa
POST /search/
{
  "yql": "select * from sources * where true"
}
#%%vespa
# basket co-occurrence
POST /search/
{
  # one sample doc
  "hits": 1,
  # say that I bought "whole milk"
  "select": {
    "where": {
      "contains": [
        "items",
        "whole milk"
      ]
    },
    # what other items are frequently bought with it?
    "grouping": [
      {
        "all": {
          "group": "items",
          "order": "-count()",
          "each": {
            "output": "count()"
          }
        }
      }
    ]
  }
}
#%%vespa
# Delete all documents
DELETE /document/v1/?selection=true&cluster=content
#%%bash
# TODO: make sure you're in the right directory
vespa feed gits/university/ranking/ch5/dataset/category_recommender/small_dataset_with_features.jsonl
#%%vespa
# which categories are available?
POST /search/
{
  "hits": 0,
  "select": {
    "where": true,
    "grouping": [
      {
        "all": {
          "group": "category",
          "each": {
            "output": "count()"
          }
        }
      }
    ]
  }
}
#%%vespa
# Global recommendations
POST /search/
{
  "yql": "select * from sources * where true",
  "ranking.features.query(user_profile)": "{\"Books\": {\"poetry\": 5, \"spirituality\": 2}, \"Electronics\":{\"USB cable\": 7}}",
  "ranking.profile": "recommendations"
}
#%%vespa
# per-category recommendations
POST /search/
{
  "yql": "select * from product where category contains 'Books'",
  "ranking.features.query(user_profile)": "{\"Books\": {\"poetry\": 5, \"spirituality\": 2}, \"Electronics\":{\"USB cable\": 7}}",
  "ranking.profile": "recommendations"
}