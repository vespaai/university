rank-profile per_doc {
# per-document lexical score

    rank chunk_ts {
        # consider all content_ts elements as a single text
        # i.e. phrases work across consecutive chunks
        element-gap: 0
    }

    rank-properties {
        ### how to compute freshness (i.e. how the logarithmic decay curve should look like)
        ## see https://docs.vespa.ai/en/reference/rank-features.html#freshness

        # ages older than 3 years don't drop score anymore
        freshness(modified_at_l).maxAge: 94672800
        # at 1 year old, score is halved
        freshness(modified_at_l).halfResponse: 31536000
    }

    function native_rank_chunk_ts() {
        expression: nativeRank(chunk_ts)
    }

    # bump fresher content
    function freshness_modified_at_l() {
        expression: freshness(modified_at_l).logscale
    }

    # bump content with more incoming links
    function normalized_links_in_count_i() {
        expression: log(1 + attribute(links_in_count_i))
    }

    summary-features: native_rank_chunk_ts freshness_modified_at_l normalized_links_in_count_i

    first-phase {
        expression: native_rank_chunk_ts() * freshness_modified_at_l() * normalized_links_in_count_i()
    }
}