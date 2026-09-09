The chatbot's streaming endpoint no longer returns a 500. Its router
authenticated with ninja's stock `django_auth`, which resolves a bare `User`
where every phoxtail endpoint now expects an `AuthorizationContext`. A test
guards the whole package against reintroducing either stock session backend.
