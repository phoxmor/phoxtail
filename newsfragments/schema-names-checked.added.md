`phoxtail.api.schema_names.clashing_schemas(api)` lists every schema name that
two apps use for different shapes, with the modules defining it. The OpenAPI
document keeps one schema per name, so such a clash silently documents one of
the two in place of the other. A package's suite passes `involving="its_package"`
to see only the clashes its own schemas take part in, and asserts the answer
is empty.
