The streams API now lives inside the streams app (`phoxtail/streams/api/`) and
is found by convention rather than mounted by hand. The endpoints, their
schemas and their auth are unchanged; only the `operationId` values in the
OpenAPI schema differ, since django-ninja derives those from the module path.
