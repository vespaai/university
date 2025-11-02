rank-profile default {
# lexical search

    function native_rank_name() {
        expression: nativeRank(ProductName)
    }
    function native_rank_description() {
        expression: nativeRank(Description)
    }

    summary-features: native_rank_name native_rank_description

    first-phase {
        expression: native_rank_name() + native_rank_description()
    }
}