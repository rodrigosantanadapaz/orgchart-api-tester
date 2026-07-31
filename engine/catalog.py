"""Endpoint catalog for the Org Chart REST API (orgchart/v1).

Derived from the generated OpenAPI contract and the tester's endpoint list.
Every endpoint in v1 is a read-only ``GET`` with no request body; the
``request_body`` field is kept on the model so the catalog can describe future
mutating endpoints without a schema change.

This module is pure data + lookup helpers. It performs no I/O and depends on
nothing else in the project.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

# Allowed vocabularies (kept small and explicit).
CATEGORIES = ("navigables", "hierarchy", "prompts")
RESPONSE_TYPES = ("navigable", "navigableCollection", "promptValues")
PARAM_LOCATIONS = ("path", "query")


@dataclass(frozen=True)
class Param:
    name: str
    location: str  # one of PARAM_LOCATIONS
    required: bool = False
    repeatable: bool = False  # true => the query param may appear multiple times
    description: str = ""
    example: str = ""


@dataclass(frozen=True)
class Endpoint:
    id: str
    method: str
    path: str  # relative to restBaseTemplate; may contain {ID}/{subresourceID}
    category: str
    summary: str
    description: str = ""
    params: List[Param] = field(default_factory=list)
    request_body: Optional[dict] = None  # None for all v1 (read-only) endpoints
    response_type: str = "navigable"

    # -- convenience accessors -------------------------------------------- #
    def path_params(self) -> List[Param]:
        return [p for p in self.params if p.location == "path"]

    def query_params(self) -> List[Param]:
        return [p for p in self.params if p.location == "query"]

    def required_path_params(self) -> List[Param]:
        return [p for p in self.path_params() if p.required]

    def param(self, name: str) -> Optional[Param]:
        for p in self.params:
            if p.name == name:
                return p
        return None


_LIMIT = Param("limit", "query", description="Max items to return.", example="20")
_OFFSET = Param("offset", "query", description="Pagination offset.", example="0")
_SEARCH = Param("search", "query", description="Type-ahead search text.")
_NAV_FILTER = Param(
    "navigableFilter",
    "query",
    repeatable=True,
    description="Filter WID(s) from the navigableFilters prompt. Repeat for multiple.",
)


ENDPOINTS: List[Endpoint] = [
    Endpoint(
        id="list_navigables",
        method="GET",
        path="/navigables",
        category="navigables",
        summary="List navigables",
        description="Returns the set of navigable org-chart nodes (orgs, workers, "
        "unfilled positions) the current user can see.",
        params=[_LIMIT, _OFFSET],
        response_type="navigableCollection",
    ),
    Endpoint(
        id="get_navigable",
        method="GET",
        path="/navigables/{ID}",
        category="navigables",
        summary="Get a navigable (self)",
        description="Returns a single navigable by its instance WID/ID.",
        params=[Param("ID", "path", required=True, description="Navigable instance ID/WID.")],
        response_type="navigable",
    ),
    Endpoint(
        id="get_children",
        method="GET",
        path="/navigables/{ID}/children",
        category="hierarchy",
        summary="Get child navigables",
        description="Direct reports / sub-orgs of the given navigable. Supports "
        "navigableFilter (WIDs from the navigableFilters prompt).",
        params=[
            Param("ID", "path", required=True, description="Parent navigable ID/WID."),
            _NAV_FILTER,
            _LIMIT,
            _OFFSET,
        ],
        response_type="navigableCollection",
    ),
    Endpoint(
        id="get_child",
        method="GET",
        path="/navigables/{ID}/children/{subresourceID}",
        category="hierarchy",
        summary="Get a single child navigable",
        params=[
            Param("ID", "path", required=True, description="Parent navigable ID/WID."),
            Param("subresourceID", "path", required=True, description="Child navigable ID/WID."),
        ],
        response_type="navigable",
    ),
    Endpoint(
        id="get_parent",
        method="GET",
        path="/navigables/{ID}/parent",
        category="hierarchy",
        summary="Get parent navigables",
        description="Parent org(s)/manager of the given navigable. Supports navigableFilter.",
        params=[
            Param("ID", "path", required=True, description="Child navigable ID/WID."),
            _NAV_FILTER,
            _LIMIT,
            _OFFSET,
        ],
        response_type="navigableCollection",
    ),
    Endpoint(
        id="get_parent_single",
        method="GET",
        path="/navigables/{ID}/parent/{subresourceID}",
        category="hierarchy",
        summary="Get a single parent navigable",
        params=[
            Param("ID", "path", required=True, description="Child navigable ID/WID."),
            Param("subresourceID", "path", required=True, description="Parent navigable ID/WID."),
        ],
        response_type="navigable",
    ),
    Endpoint(
        id="prompt_organizations",
        method="GET",
        path="/values/orgChartPrompts/organizations/",
        category="prompts",
        summary="Prompt: organizations",
        description="Searchable list of organizations valid as a navigable context.",
        params=[Param("search", "query", description="Type-ahead search text.", example="Global"),
                _LIMIT, _OFFSET],
        response_type="promptValues",
    ),
    Endpoint(
        id="prompt_workers",
        method="GET",
        path="/values/orgChartPrompts/workers/",
        category="prompts",
        summary="Prompt: workers",
        description="Searchable list of workers valid as a navigable context.",
        params=[Param("search", "query", description="Type-ahead search text.", example="Logan"),
                _LIMIT, _OFFSET],
        response_type="promptValues",
    ),
    Endpoint(
        id="prompt_navigable_filters",
        method="GET",
        path="/values/orgChartPrompts/navigableFilters/",
        category="prompts",
        summary="Prompt: navigableFilters",
        description="Valid WIDs for the navigableFilter query parameter on children/parent.",
        params=[Param("search", "query", description="Type-ahead search text.", example="Manager"),
                _LIMIT, _OFFSET],
        response_type="promptValues",
    ),
]

_BY_ID: Dict[str, Endpoint] = {e.id: e for e in ENDPOINTS}


def by_id(endpoint_id: str) -> Optional[Endpoint]:
    return _BY_ID.get(endpoint_id)


def as_dicts() -> List[dict]:
    """JSON-serializable view of the catalog (for later UI consumption)."""
    return [asdict(e) for e in ENDPOINTS]
