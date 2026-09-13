Deleting a collection now asks Wagtail what is inside it, instead of counting
images, documents and media itself. `describe_collection_contents` is the hook
Wagtail's own delete view uses and the extension point any installed app may
register against, so the API refuses exactly what the admin refuses — including
contents belonging to apps this code knows nothing about.

Two consequences. A collection holding objects contributed by another app is now
refused where it would previously have been deleted along with them. And because
`describe_collection_children` reports the whole subtree rather than direct
children, a collection whose only descendant is a grandchild is now refused too;
it was deletable before.
