#!/bin/sh

echo "Put a document:"
(
	set -x
	vespa document put "id:ecommerce:product::42" dummy-document.json
)

echo "Get it back:"
(
	set -x
	vespa document get "id:ecommerce:product::42"
)

echo "Try to find it with a query:"
(
	set -x
	vespa query 'select * from product where ProductName contains "everything"' | jq .root.children
)

echo "Now remove it again:"
(
	set -x
	vespa document remove "id:ecommerce:product::42"
)

echo "Check that it is gone:"
(
	set -x
	vespa query 'select * from product where ProductName contains "everything"' | jq .root.children
)
