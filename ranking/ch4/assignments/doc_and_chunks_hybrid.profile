rank-profile doc_and_chunks_hybrid inherits per_doc, per_chunk_lexical, per_chunk_semantic {

    function chunk_hybrid_scores() {
        # Not all chunks have a text score, so we need to merge the scores
        # i.e. consider chunks without a text score as having a score of 0.
        # By contrast, a simple chunk_sim_scores+normalized_chunk_text_scores would
        # use a join and consider chunks that have both text and semantic scores.
        # Tensor playground example: https://docs.vespa.ai/playground/#N4KABGBEBmkFxgNrgmUrWQPYAd5QFNIAaFDSPBdDTAO30lqwCcBbAQwBsBLALwIAmAfQBGrAEwBWEmRqQiCSABcCtAM4sAFAGMAFgFdaAa2ABfAJRxgAHVoRrkAIwOEABgB0k4rfuRxLsA9HbzswBwAWAI8ATltTSFkIU1lTUgxqclwGIjS5SjREugZtLDVuWgIhMtZuTnZmbiVuAjUZGkwFKBV1LT1DEwsrHzCnKPcAdhDff3wPAGYpkbmx6MWIsf9aeMLkjFTZDMwsxW02vPxD8iUGADksJu0CMF0sAHcwAk4CVlUlMDmwNw1GAmH9ymAlLonmp9KxiGARARtOx9GonpDobCwKiWmB2GAAFZYcGGAQEZgQqHPLBYATuBLtXaofbpQrYfLyM7kfKXIqKV7MLC0ADmVVhXLknUYLA4PH4wjEUjAAGowCUyhUqtwanUGk0WgyaEykrkILz2cUJRAKBdCtbrooAMrsH54tRwQ17FKmgrtC2KHJsnl2qD0fmCkViiRWjoMInlTTDdXlSrVWr1RrNNTwphsLh8QSiCReYbQTTVeEqAAeSnM5e1KohBBr5ls5k9zO9BzZxygpx91uD7XtDAAKlgIewjE8uJwPl8frQlNmwK8nhVBHiwD9mMKnuU1Cp2AIwFhoFv47R6Tsu6y-b3OQOoEPh4xiixmEilEIlPcuDHrSlHc90TUJk01NNdUzFocxlfN5SLKRFjLCsmxbetWEbatazbDskhSFAAF0QFMIA
        expression {
            # TODO expression that adds up lexical and semantic scores for each chunk
            # making sure to consider chunks without a text score as having a score of 0.
            # Output should be a tensor like:
            # {
            #     "type": "tensor(chunk{})",
            #     "cells": {
            #         "1": 0.5112776,
            #         "2": 1.1021805,
            #         "3": 0.75621805,
            #         "4": 0.3451276
            #     }
            # }
        }
    }

    # we use this in the summary definition to only fetch the top 3 chunks per document
    function top_3_chunk_hybrid_scores() {
        expression: # TODO
    }

    summary-features {
        # from per_doc
        native_rank_chunk_ts
        native_rank_article_title
        freshness_modified_at_l
        normalized_links_in_count_i
        closeness_article_title

        # from per_chunk_semantic
        top_3_chunk_sim_scores
        avg_top_3_chunk_sim_scores

        # from per_chunk_lexical
        top_3_chunk_bm25_scores
        avg_top_3_normalized_bm25

        # top 3 chunks by hybrid score
        top_3_chunk_hybrid_scores
    }
    
    first-phase {

        # NOTE: the weights are not optimized yet
        # we could also use a model to generate a score from these features, like in ch3
        # and/or use it as a reranker
        expression {
            native_rank_chunk_ts() +
            3*native_rank_article_title() +
            freshness_modified_at_l() +
            normalized_links_in_count_i() +
            3* closeness_article_title() +
            avg_top_3_normalized_bm25() +
            3*max_normalized_bm25() +
            avg_top_3_chunk_sim_scores() +
            3*max_chunk_sim_score()
        }
    }
}