"""Each door is documented once in the OpenAPI schema, as itself.

ninja names a security scheme after the auth object's class. Both halves of
``guarded()`` wrap a different backend in the same ``Authorize``, so under
one name the token door and the session door overwrote each other, and
every annotated endpoint advertised whichever was written last — a cookie
on one project, a header on the next, depending on which apps happened to
be installed. A client generated from that schema sends the wrong
credential, or none.
"""

from __future__ import annotations

from ninja import NinjaAPI

from phoxtail.api.auth import Authorize, PhoxtailSessionAuth, authenticated, guarded, has_no_ceiling
from phoxtail.tokens.ninja import PhoxtailTokenAuth

BOTH_DOORS = [{"PhoxtailTokenAuth": []}, {"PhoxtailSessionAuth": []}]


def _schema():
    api = NinjaAPI(
        urls_namespace="test_openapi_security",
        auth=[Authorize(PhoxtailTokenAuth(), has_no_ceiling), PhoxtailSessionAuth()],
    )

    @api.get("/guarded/", auth=guarded("phoxtail_users.view_user"))
    def guarded_endpoint(request):
        return {}

    @api.get("/default/")
    def default_endpoint(request):
        return {}

    # Last, so a session door written last would win under a shared name.
    @api.get("/open/", auth=authenticated())
    def open_endpoint(request):
        return {}

    return api.get_openapi_schema(path_prefix="")


def _security(schema, path):
    return schema["paths"][path]["get"]["security"]


def test_the_schema_names_the_two_real_doors():
    schemes = _schema()["components"]["securitySchemes"]

    assert set(schemes) == {"PhoxtailTokenAuth", "PhoxtailSessionAuth"}
    assert schemes["PhoxtailTokenAuth"]["in"] == "header"
    assert schemes["PhoxtailSessionAuth"]["in"] == "cookie"


def test_every_endpoint_lists_both_doors_whatever_wraps_them():
    schema = _schema()

    for path in ("/guarded/", "/default/", "/open/"):
        assert _security(schema, path) == BOTH_DOORS, path


def test_a_wrapped_door_is_still_an_authorize():
    door = Authorize(PhoxtailTokenAuth(), has_no_ceiling)

    assert isinstance(door, Authorize)
    assert type(door) is type(Authorize(PhoxtailTokenAuth(), has_no_ceiling))
