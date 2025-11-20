rank-profile per_doc {

    #########################################################
    ### lexical score
    #########################################################
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

    function native_rank_article_title() {
        expression: nativeRank(article_title_t)
    }

    # bump fresher content
    function freshness_modified_at_l() {
        expression: freshness(modified_at_l).logscale
    }

    # bump content with more incoming links
    function normalized_links_in_count_i() {
        # Normalizes the number of incoming links to a value between 0 and 1.
        # Because atan(x) returns a value between -π/2 and π/2. In our case,
        # links_in_count_i is always positive, so atan(x) will be between 0 and π/2.
        # 100 defines the value for links_in_count_i where the middle of the curve is (0.5),
        # because atan(1) is π/4. After this, atan(x) grows asymptotically to π/2.
        # For the curve itself, see https://commons.wikimedia.org/wiki/File:Arctangent.svg
        # Tensor playground example: https://docs.vespa.ai/playground/#N4KABGBEBmkFxgNrgmUrWQPYAd5QFNIAaFDSPBdDTAO30gBsBLWgawGcB9VrgYywBXWgBceJMjUhEEkAJwAGBZEkQAvpLWkM1crgZFtUymlV0GtLACcAtgEMWALwIATLi3bdeA4WOYSaTBkoOxE7WgAKD04eWn4hUR4wAHowAEYlAEowACowACZkgGYAOjSAFjSAVjl8gDYqoqqADjkAdjkilUCNDF6wAF0QNSA
        expression: atan(attribute(links_in_count_i) / 100) * 2/3.141592653589793
    }

    #########################################################
    ### semantic score
    #########################################################
    inputs {
        query(q_embedding) tensor<float>(x[384])
    }

    function closeness_article_title() {
        expression: closeness(field, article_title_embedding)
    }

    #########################################################
    # print the output of these functions, for debugging/transparency
    summary-features {
        native_rank_chunk_ts
        native_rank_article_title
        freshness_modified_at_l
        normalized_links_in_count_i
        closeness_article_title
    }

    # we can combine these in many ways (e.g., multiply, boost, log, etc.)
    # we add them up for now
    first-phase {
        expression {
            native_rank_chunk_ts() +
            2*native_rank_article_title() +
            freshness_modified_at_l() +
            normalized_links_in_count_i() +
            closeness_article_title()
        }
    }
}