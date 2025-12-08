rank-profile per_doc {

    #########################################################
    ### lexical score
    #########################################################
    rank chunk_ts {
        # consider all content_ts elements as a single text
        # i.e. phrases work across consecutive chunks
        element-gap: 0
    }

    function native_rank_chunk_ts() {
        expression: nativeRank(chunk_ts)
    }

    function native_rank_article_title() {
        expression: nativeRank(article_title_t)
    }

    rank-properties {
        ### how to compute freshness (i.e. how the logarithmic decay curve should look like)
        ## see https://docs.vespa.ai/en/reference/rank-features.html#freshness

        # at 3 years old, score is 0. It doesn't drop to negative
        freshness(modified_at_l).maxAge: 94672800
        # at 1 year old, score is halved
        freshness(modified_at_l).halfResponse: 31536000
    }

    # bump fresher content
    function freshness_modified_at_l() {
        expression: freshness(modified_at_l).logscale
    }

    # bump content with more incoming links
    function normalized_links_in_count_i() {
        # Normalizes the number of incoming links to a value between 0 and 1.
        # Tensor playground example: https://docs.vespa.ai/playground/#N4KABGBEBmkFxgNrgmUrWQPYAd5QFNIAaFDSPBdDTAO30gBsBLWgawGcB9VrgYywBXWgBceJMjUhEEkAJwAGBZEkQAvpLWkM1crgZ8JNKJTSrMIhgAMAhiJu0AFAA8AlFbAAnAiMGfaHGA2YABuNoyCBGAARj4A7gQEtGBWALSAA8AA9ABMHg4AJilZuQB0ADq0FQCSyUKeYHw2HATEKSzs3LwCwmLMHsyB4XE2AJ6BOFgczCLMIS1gHFgpdg4u7mBxzIyMMVGxIglJKQp5tIVWxVbllbRWAIxKHvkE0KwEgSIAFlFhEVHQWHqVnanB4tH4QlEPA8cW+3jAXyiAFtmPl8owolhoAjvg0-HMwAMwI4FCUAKyuVqxRqCZrLexOO6uMAAXjAWQALFcKhUAILQEQEepfAatWwMtYeADmniwcUGHBGSJwIiwM0a2xGCKWFxyVjgPNoAEJECtknx8QQALqOT4iEQ4DhwTKZQQ4RhYGz5EqbNjMJEEfLMGwlQFSzK+5g4QPBzICJFIrABTJfQRI6KZAiZ7KZXmePgMqVJEQlDghcMAdg5AGYcM5UnmCw4i6JS+WSjhaFLXCpjBoMFpJLpMPpZERtFJTMPyPRZLRAUjwswAF6Brggzrg7pQ5hGYyEBhmxwbsEQno8MCZMAPBTMgBUYBz1ZKdw5dzJcmyADYydWyQAOOQKzkatexoftUAgq0QDUIA
        expression {
            # TODO expression that normalizes links_in_count_i
        }
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