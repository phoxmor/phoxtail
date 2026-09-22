The API documentation describes the streams variant-collection endpoints
(`/api/streams/v1/collections/`) with their own schemas again. They shared the
names `CollectionCreate` and `CollectionList` with the cms (Wagtail) collection
schemas, and the document showed one in place of the other. The streams
schemas are now named `VariantCollection*`, after the model; request and
response bodies are unchanged.
