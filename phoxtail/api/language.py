"""The language the API answers a program in.

Django picks one language per request, from the URL, the language cookie,
the browser's ``Accept-Language`` or the site's default, and it cannot tell
a person from a program. The API can: a caller holding a token is a
program, whose reader works against an English schema. So a program reads
English unless it asks otherwise, and a browser session keeps the language
its person chose.
"""

from __future__ import annotations

from django.utils import translation

# Django's own parser, though private: no public API reads the header
# alone, and this one carries Django's guard against oversized headers.
from django.utils.translation.trans_real import parse_accept_lang_header

PROGRAM_LANGUAGE = "en"


def program_language(request) -> str:
    """The language a program asked for in ``Accept-Language``, or English.

    Only the header counts. The language cookie is a choice a person made
    in a browser, and the site's default is chosen for its visitors;
    neither was asked for by the program.
    """
    for code, _quality in parse_accept_lang_header(request.headers.get("Accept-Language", "")):
        if code == "*":
            break
        try:
            return translation.get_supported_language_variant(code)
        except LookupError:
            continue
    return PROGRAM_LANGUAGE


def speak_to_program(request) -> None:
    """Answer the rest of this request in :func:`program_language`.

    It holds until the request ends; ``LocaleMiddleware`` picks afresh for
    the next one.
    """
    language = program_language(request)
    translation.activate(language)
    request.LANGUAGE_CODE = language
