rank-profile preferences {
    inputs {
        query(user_preferences) tensor<float>(features{})
    }

    function my_bm25() {
        expression: bm25(ProductName)
    }

    function my_nativeRank() {
        expression: nativeRank(Description) * 1.7
    }

    summary-features: my_bm25 my_nativeRank

    first-phase {
        expression: (my_bm25() + my_nativeRank()) * attribute(AverageRating)
    }

    second-phase {
        rerank-count: 10
        expression: sum(query(user_preferences) * attribute(ProductFeatures))
    }
}