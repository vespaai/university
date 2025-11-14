rank-profile per_chunk_hybrid inherits per_chunk_lexical {
    
    # TODO
    first-phase {
        expression {
            native_rank_chunk_ts() # native rank across all chunks
            + freshness_modified_at_l() # bump fresher content
            + normalized_links_in_count_i() # bump content with more incoming links 
            + avg_top_N_chunk_text_scores(3)
            + 3*max_chunk_text_score(3) # highest scoring chunk (by BM25) gets more weight
        }
    }
}