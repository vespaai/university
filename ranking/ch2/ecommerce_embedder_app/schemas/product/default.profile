rank-profile default {

    # lexical search
    first-phase {
        expression: nativeRank(ProductName,Description)
    }
}