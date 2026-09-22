"""One name, one schema, across every app the API mounts.

The property worth protecting: two different schemas never share a name,
because the OpenAPI document would silently describe one of them twice.
"""

from __future__ import annotations

from ninja import NinjaAPI, Router, Schema

from phoxtail.api import api
from phoxtail.api.schema_names import clashing_schemas


def _api(*views):
    test_api = NinjaAPI(urls_namespace="schema-names-test")
    for index, (response, body) in enumerate(views):
        router = Router()

        def view(request, payload):
            return None

        # Set directly: this module postpones annotations, and a loop
        # variable cannot be looked up by name afterwards.
        view.__annotations__ = {"payload": body}
        router.post("/", response=response)(view)
        test_api.add_router(f"/app{index}/", router)
    return test_api


def _schema(class_name, **fields):
    return type(class_name, (Schema,), {"__annotations__": fields, "__module__": f"tests.{class_name}"})


class TestClashingSchemas:
    def test_two_shapes_under_one_name_clash(self):
        one = _schema("Thing", name=str)
        two = _schema("Thing", name=str, size=int)

        found = clashing_schemas(_api((one, _schema("In", a=str)), (two, _schema("In", a=str))))

        assert list(found) == ["Thing"]

    def test_identical_copies_do_not(self):
        one = _schema("Thing", name=str)
        two = _schema("Thing", name=str)

        assert clashing_schemas(_api((one, _schema("In", a=str)), (two, _schema("In", a=str)))) == {}

    def test_a_request_body_clash_is_found(self):
        found = clashing_schemas(
            _api((_schema("Out", a=str), _schema("Body", a=str)), (_schema("Out", a=str), _schema("Body", b=int)))
        )

        assert list(found) == ["Body"]

    def test_a_nested_clash_is_found(self):
        inner_one = _schema("Inner", a=str)
        inner_two = _schema("Inner", b=int)
        outer_one = _schema("OuterOne", items=list[inner_one])
        outer_two = _schema("OuterTwo", item=inner_two)

        found = clashing_schemas(_api((outer_one, _schema("In", a=str)), (outer_two, _schema("In", a=str))))

        assert list(found) == ["Inner"]

    def test_every_module_is_named(self):
        found = clashing_schemas(
            _api(
                (_schema("Thing", a=str), _schema("In", a=str)),
                (_schema("Thing", b=int), _schema("In", a=str)),
            )
        )

        assert found == {"Thing": ["tests.Thing"]}

    def test_a_package_sees_only_its_own_clashes(self):
        mine = type("Thing", (Schema,), {"__annotations__": {"a": str}, "__module__": "somepkg.api.schemas"})
        theirs = type("Thing", (Schema,), {"__annotations__": {"b": int}, "__module__": "otherpkg.api.schemas"})
        elsewhere_one = type("Other", (Schema,), {"__annotations__": {"a": str}, "__module__": "otherpkg.one"})
        elsewhere_two = type("Other", (Schema,), {"__annotations__": {"b": int}, "__module__": "otherpkg.two"})
        test_api = _api((mine, _schema("In", a=str)), (theirs, elsewhere_one), (_schema("Out", a=str), elsewhere_two))

        assert set(clashing_schemas(test_api)) == {"Thing", "Other"}
        assert set(clashing_schemas(test_api, involving="somepkg")) == {"Thing"}
        assert clashing_schemas(test_api, involving="some") == {}

    def test_views_with_different_parameters_do_not_clash(self):
        # ninja wraps every view's query parameters in a model called
        # QueryParams; it is never documented under that name.
        test_api = NinjaAPI(urls_namespace="schema-names-params")
        router = Router()

        @router.get("/one/", response=_schema("Out", a=str))
        def one(request, page: int = 1):
            return None

        @router.get("/two/", response=_schema("Out", a=str))
        def two(request, search: str = ""):
            return None

        test_api.add_router("/", router)

        assert clashing_schemas(test_api) == {}


# Clashes that exist today, each removed by the commit that resolves it; the
# test fails on a new clash and on an entry left behind after its fix.
KNOWN = {"BlockUpdate", "CollectionCreate", "CollectionList", "Error"}


def test_no_new_schema_name_clashes():
    found = clashing_schemas(api)
    assert set(found) == KNOWN, found
