rank-profile bm25chunk {
    first-phase {
        expression: bm25(chunk_ts)
    }
}