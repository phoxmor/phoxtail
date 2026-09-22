The API documentation describes the page-body block endpoints
(`/api/cms/v1/pages/{id}/blocks/`) with their own schemas again. They shared
the name `BlockUpdate` with the streams block-definition schema, and the
document showed one in place of the other. The page-body schemas are now named
`BodyBlock*`; request and response bodies are unchanged.
