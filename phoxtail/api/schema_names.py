"""One name, one schema, across every app the API mounts.

The OpenAPI document keeps its schemas in one namespace keyed by class
name, and ninja merges them without checking. Two apps that each define a
different ``CollectionCreate`` therefore document one of them twice and
the other never, and nothing fails. :func:`clashing_schemas` is the check.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterator
from typing import Any, get_args

from ninja import NinjaAPI
from ninja.constants import NOT_SET
from ninja.params.models import ParamModel
from pydantic import BaseModel


def _operations(api: NinjaAPI) -> Iterator[Any]:
    # The routers mounted on *api*, flattened the way ninja flattens them
    # to build the document.
    for prefix, router in api._routers:
        for mount in router.build_routers(prefix):
            for view in mount.template.path_operations.values():
                yield from view.operations


def _models(annotation: Any, found: set[type[BaseModel]]) -> None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if annotation in found:
            return
        # ninja's own containers for a view's query, path and body
        # parameters are never documented under their names; what they hold is.
        if not issubclass(annotation, ParamModel):
            found.add(annotation)
        for field in annotation.model_fields.values():
            _models(field.annotation, found)
    for argument in get_args(annotation):
        _models(argument, found)


def clashing_schemas(api: NinjaAPI, involving: str | None = None) -> dict[str, list[str]]:
    """Each schema name that stands for more than one shape, with every module
    defining it under that name.

    Identical copies under one name are not a clash — the document is right
    whichever it keeps. *involving* narrows the answer to clashes a module
    under that package takes part in, so a package's suite can assert on its
    own schemas while phoxtail's apps are mounted beside it.
    """
    found: set[type[BaseModel]] = set()
    for operation in _operations(api):
        for model in operation.response_models.values():
            if model is not None and model is not NOT_SET:
                _models(model.__annotations__["response"], found)
        for model in operation.models:
            _models(model, found)

    shapes: dict[str, set[str]] = defaultdict(set)
    modules: dict[str, set[str]] = defaultdict(set)
    for model in found:
        shapes[model.__name__].add(json.dumps(model.model_json_schema(), sort_keys=True))
        modules[model.__name__].add(model.__module__)

    clashes = {name: sorted(modules[name]) for name, shape in shapes.items() if len(shape) > 1}
    if involving is not None:
        prefix = involving + "."
        clashes = {
            name: owners
            for name, owners in clashes.items()
            if any(owner == involving or owner.startswith(prefix) for owner in owners)
        }
    return clashes
