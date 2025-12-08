rank-profile per_chunk_semantic {

    inputs {
        query(q_embedding) tensor<float>(x[384])
    }

    # Computes the dot product of the query embedding with each chunk embedding.
    # Returns a tensor with a similarity score for each chunk ID. E.g.,
    #{
    #    "type": "tensor(chunk{})",
    #    "cells": {
    #        "1": 0.8,   # e.g., this is the dot product of the query embedding with the first chunk embedding
    #        "2": 0.3
    #    }
    #}
    # For a demo, check https://docs.vespa.ai/playground/#N4KABGBEBmkFxgNrgmUrWQPYAd5QFNIAaFDSPBdDTAO30gEcB9AgWwCMCATbgS1oBzEmRqQiCSABcCtAM5YATgAoAHogDMAXQCUcRAAYAdAHYDJ4mGMBWSza2RREAL6jnpDNXK4GRD2Mo0JzoGAGMACwBXWgBrVk4efiE5ERpMCSgZeSVlCOiY4HcwdW09YAAdWghyyABGGoRDU3M7I1tUe0sIAGIwPm5ZKT5QgEMAGzApLDBGSIJFAE8wQCTCMFCsOQECMEAJIjBaowNK6sgAJgakGy6rZosb6y1r3rkRtm2x2UEpcMt+aGh5oMwPxFARQkMsLRjmAahoLk12hArh1bo8wM9Xu9Pt9fnx-oDaFJgXxQeC+JDoTUACzw4xmO7IsAAWnsGAxbzAHyEOLAOBGiiG4zGS1wOA2fBkYEhnJGciJ-DYlWcjjSrgw7lEXkwPkkfmCFHwWvI9F1HzehIA7nw5ARmGxImMhjgxsMRhD6P40uIGCx2FxeAJBGAAFRrKKxeL+pKCFLBNWoDWefU6wipAKG4IQSAmqDcLBSZg4RRYbiRcFpr0ZSCg0uhAjKX0JANCENh-KRxKBuSWOSRNiWVQ6FU0eMuT1BL0pyChCuYQJGzBSBjdbp5qRMoslstEgC8a3FtG2mzYfDG-IlC0qlQAQmCRpEbWAAG5gqaKORgcIjF+TcJHzFgAAMqcYC0EobBgMoACiZYugMIxVFyXzhDoRhXrQACEiDrJsh5gMep7nlICxaMo4RSFIOByHAAD0NGRM6WAjNwRhWjEfBvPwIxGEogg0WxfA4DwfAjDR6xsGwkJyDRJgyacNEAMqjGeiibrWUhGIIeI6OhgEEFIADkH7iTgkSSt8bqcti4QIL2EFYNA+GzPyBAfg5YBCsS5qbFJliedEAyKE5kQuWAxb5kYYAAOoSuEkwWtMCqyD58iWAsWCRAZ3DAtMEpgFa3y-tsOALBZghKAQCFFRVbBoVCmGIAQsH9JVVT8HKCF1qR5GUdRdEMWMTEsQJnEiTxih8QJQlcWJWASVJNHfH2HA0dYq1rTBoRwa1zDtVInW2qcLFyE+fEaAAbAYOCqEym3bQhu3WvttB1swR1GCdghGDgQhDnGbjjgu2CBN645ZvOmZQDm4jNfBtDMGBihsCkYPpAwciMAKyh2coYoWrk4ZxH6nbJJYpw6AOOh-aqAOasmIMzqjBpUJD0gMAA8t88xWjalgcHwgiCPMz6vkoH5WmMEwAFYPkSX4-uEAt-kFa68sW6nUcO6q00mk4g3qXoQ2kWbQxElUFnksSzuQVZZAoKiWwURQlLocAVFUMJ1LStytIi9yPJSZze37dItP7xCB3C+AItcjI3PSAce9S3v0r7XQsm0icnGbbrzPCJiHJY1iFxAxcGFoSpawmOuoEDU4G+mLPG1DDBroW6vbswBXhMwOcyIo1to5INZlvWjZRoGrZ973hM9n2lNVy4bgoFoIDOEAA
    function chunk_sim_scores() {
        expression: reduce(query(q_embedding) * attribute(chunk_embeddings), sum, x)
    }
    # NOTE: since these vectors are normalized (services.xml's normalize=true), the dot product is the cosine similarity

    # Returns a tensor with the top 3 chunk IDs by their cosine similarity scores.
    function top_3_chunk_sim_scores() {
        expression: top(3, chunk_sim_scores())
    }

    # Returns the average of the top 3 chunks' cosine similarity scores.
    function avg_top_3_chunk_sim_scores() {
        expression: reduce(top_3_chunk_sim_scores(), avg, chunk)
    }

    # Returns the maximum of the chunk cosine similarity scores.
    function max_chunk_sim_score() {
        expression: reduce(chunk_sim_scores(), max, chunk)
    }

    summary-features {
        chunk_sim_scores
        top_3_chunk_sim_scores
        avg_top_3_chunk_sim_scores
    }

    first-phase {
        expression {
            avg_top_3_chunk_sim_scores()
            + 3*max_chunk_sim_score() # highest scoring chunk (by cosine similarity) gets more weight
        }
    }
}