The image, document, video and audio endpoints at `/api/media/v1/` asked for
nothing beyond being authenticated, so any account could list every file on the
site, download one, move it between collections, or delete it. They now ask
Wagtail the same questions its own admin asks, in the same order: permissions on
files are granted per collection, and a grant covers that collection and
everything beneath it.

A listing narrows to what the caller may see rather than refusing, and a file
they may not see answers `404` rather than `403` — both copied from Wagtail's
chooser, the second so that nobody without a grant can map the library by
telling the two answers apart. Uploading asks about the destination collection,
and so does moving a file into one. Changing and deleting ask about that one
file, and Wagtail's ownership rule comes with them: holding only `add` in a
collection still permits changing and deleting the files you uploaded yourself.
Fetching an image's bytes asks for `change`, which is what Wagtail requires
before serving one, rather than the lighter permission that lists it.

Fetching an image whose file is an SVG also stopped failing. The endpoint asked
Wagtail for a JPEG rendition, which it refuses for a vector file, so `/view/`
answered `500` for every SVG in the library — most logos. It now names
`preserve-svg`, Wagtail's own directive for the case, and returns the SVG
unchanged.
