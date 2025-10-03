rank-profile closeness_productname_description {
    inputs {
        query(q_embedding) tensor<float>(x[384])
    }

    # compute simialrity between query and both fields
    function closeness_productname() {
        expression: closeness(field, ProductName_embedding)
    }
    function closeness_description() {
        expression: closeness(field, Description_embedding)
    }

    # sum the similarities for now. We'll look at boosting and hybrid later.
    first-phase {
        expression: closeness_productname() + closeness_description()
    }

    # for debugging - expose the similarities in search results
    summary-features: closeness_productname closeness_description
}