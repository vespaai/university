rank-profile hybrid {
# get the scoring components

    ## lexical search
    function native_rank_name() {
        expression: nativeRank(ProductName)
    }
    function native_rank_description() {
        expression: nativeRank(Description)
    }

    ## semantic search
    inputs {
        query(q_embedding) tensor<float>(x[384])
    }

    function closeness_productname() {
        expression: closeness(field, ProductName_embedding)
    }
    function closeness_description() {
        expression: closeness(field, Description_embedding)
    }

    ## document attributes (needed for reranking and model training)
    function AverageRating() {
        expression: attribute(AverageRating)
    }
    function Price() {
        expression: attribute(Price)
    }

    ## show the scoring components in search results (needed for reranking and model training)
    summary-features: native_rank_name native_rank_description closeness_productname closeness_description

    ## basic hybrid ranking
    first-phase {
        expression: native_rank_name() + native_rank_description() + closeness_productname() + closeness_description()
    }
}