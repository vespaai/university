rank-profile per_chunk_lexical {
    
    # Creates a tensor with a single mapped dimension (i.e., the chunk ID)
    # and the BM25 score for each element of the chunk_ts array. Returns something like:
    #{
    #    "type": "tensor(chunk{})",
    #    "cells": {
    #        "1": 0.5112776,
    #        "2": 1.1021805
    #    }
    #}
    function chunk_bm25_scores() {
        expression: elementwise(bm25(chunk_ts),chunk,float)
    }

    # Takes each chunk's BM25 score and normalizes it to a value between 0 and 1.
    # Similar method to normalizing as in per_doc.profile, but we apply it for all chunks.
    # bm25_scale defines the value for BM25 where the middle of the curve is (0.5).
    # Playground example: https://docs.vespa.ai/playground/#N4KABGBEBmkFxgNrgmUrWQPYAd5QFNIAaFDSPBdDTAO30gCMBbAJgFYBnAYywCcCnEmRqQiCSABcCtTvwAU3ABYBXWgGtgAXwCUcYAB1aEA5ACMphGYDsAOnbEjJyK0tgADLbOPjYUwGY3AA5bax9nABY3AE53dzNQ9iMtSBEILREtUgxqclwGImzRSjQ0ugZafmYAQwAbAEsALwIAEwB9Fg5hGkxxKGrJatp5Tq5eAU4wAHowIJ0wACowVin-LwizdmjWADZ2f3Yg6Oto-1SejIwskVzMfIlCsop8W-J6CUlcM6KesQZPnDyfzESp8GoNZrtUY6c40S6oa45J73QjdYovMoQSDvfoANwA5m0Ad9MaiJAIWipuAR5MTiGBqgT6co1OoYWV4ekfqVfii-tysSVXuUJDUAB5o359SAUqk00HgpqtDpsBxgcXM1QadkXTIoAC6IC0QA
    function normalized_chunk_bm25_scores(bm25_scale) {
        expression {
            atan(chunk_bm25_scores / bm25_scale) * 2/3.141592653589793
        }
    }

    # Returns a tensor with the top 3 chunk IDs by their BM25 lexical scores. E.g.,
    #{
    #    "type": "tensor(chunk{})",
    #    "cells": {
    #        "3": 3.8021805,
    #        "5": 1.1021805,
    #        "2": 0.5112776
    #    }
    #}
    function top_3_chunk_bm25_scores() {
        # the "8" here should be the median, or a reasonably high BM25 score for us
        expression: top(3, normalized_chunk_bm25_scores(8))
    }

    # Returns the average of the top 3 chunks' BM25 scores.
    function avg_top_3_normalized_bm25() {
        expression: reduce(top_3_chunk_bm25_scores(), avg, chunk)
    }
    
    # Returns the maximum of the chunk BM25 lexical scores.
    function max_normalized_bm25() {
        expression: reduce(top_3_chunk_bm25_scores(), max, chunk)
    }

    summary-features {
        chunk_bm25_scores
        normalized_chunk_bm25_scores(8)
        top_3_chunk_bm25_scores
        avg_top_3_normalized_bm25
    }
    
    first-phase {
        expression {
            avg_top_3_normalized_bm25()
            + 3*max_normalized_bm25() # highest scoring chunk (by BM25) gets more weight
        }
    }
}