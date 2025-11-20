#%%vespa
#H1 How does data look like?
POST https://fdfdb38c.dd11e0c7.z.vespa-app.cloud/search/
{
  "yql": "select * from article where true"
}
#%%vespa
#H1 Hybrid search on article as a whole
POST https://fdfdb38c.dd11e0c7.z.vespa-app.cloud/search/
{
  "yql": "select * from article where ({targetHits:100}nearestNeighbor(article_title_embedding,q_embedding)) OR userQuery()",
  "query": "binary entropy",
  "input.query(q_embedding)": "embed(@query)",
  "ranking.profile": "per_doc"
}
#%%vespa
#H1 Lexical search per chunk
POST https://fdfdb38c.dd11e0c7.z.vespa-app.cloud/search/
{
  "yql": "select * from article where userQuery()",
  "query": "binary entropy",
  "ranking.profile": "per_chunk_lexical",
  "summary": "top_3_chunks_bm25"
}
#%%vespa
#H1 Semantic search per chunk
POST https://fdfdb38c.dd11e0c7.z.vespa-app.cloud/search/
{
  "yql": "select * from article where {targetHits:100}nearestNeighbor(chunk_embeddings,q_embedding)",
  "query": "binary entropy",
  "input.query(q_embedding)": "embed(@query)",
  "ranking.profile": "per_chunk_semantic",
  "summary": "top_3_chunks_semantic"
}
#%%vespa
#H1 Article+chunk hybrid search
POST https://fdfdb38c.dd11e0c7.z.vespa-app.cloud/search/
{
  "yql": "select * from article where ({targetHits:100}nearestNeighbor(article_title_embedding,q_embedding)) OR ({targetHits:100}nearestNeighbor(chunk_embeddings,q_embedding)) OR userQuery()",
  "query": "binary entropy",
  "input.query(q_embedding)": "embed(@query)",
  "ranking.profile": "doc_and_chunks_hybrid",
  "summary": "top_3_chunks_by_hybrid_score"
}