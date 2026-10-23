The shared test settings (`phoxtail.core.testing`) list phoxtail's apps first,
before Django, allauth and Wagtail, as a project does. A package's tests built
on them now draw phoxtail's versions of allauth's and Wagtail's templates, the
ones a site shows, and read phoxtail's translations first.
