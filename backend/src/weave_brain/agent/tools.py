from typing import Any

from weave_brain.core.config import get_settings
from weave_brain.graph import fixtures
from weave_brain.graph.queries import (
    find_experts,
    get_blast_radius,
    get_decisions_for_service,
    get_neighborhood,
    get_service_overview,
)

__all__ = [
    "TOOL_REGISTRY",
    "ToolExecutionError",
    "ToolNotFoundError",
    "call_tool",
    "find_experts",
    "get_blast_radius",
    "get_decisions_for_service",
    "get_neighborhood",
    "get_service_overview",
    "get_tool_descriptions",
]


class ToolNotFoundError(Exception):
    pass


class ToolExecutionError(Exception):
    pass


TOOL_REGISTRY: dict[str, dict] = {
    "get_service_overview": {
        "description": (
            "Ownership, team members, repos, dependencies, "
            "and linked decisions for a service."
        ),
        "required_params": ["service_id"],
        "fn": lambda service_id: (
            fixtures.get_catalog_overview_stub(service_id)
            if get_settings().development_fixtures
            else get_service_overview(service_id)
        ),
    },
    "get_blast_radius": {
        "description": (
            "All services that depend on this service with hop depth "
            "and owning teams. Use for impact and breakage questions."
        ),
        "required_params": ["service_id"],
        "fn": lambda service_id: (
            fixtures.get_catalog_blast_stub(service_id)
            if get_settings().development_fixtures
            else get_blast_radius(service_id)
        ),
    },
    "get_decisions_for_service": {
        "description": (
            "Architecture decisions, their rationale, and motivating incidents."
        ),
        "required_params": ["service_id"],
        "fn": lambda service_id: (
            fixtures.get_catalog_decisions_stub(service_id)
            if get_settings().development_fixtures
            else get_decisions_for_service(service_id)
        ),
    },
    "find_experts": {
        "description": (
            "People who worked on projects using this service. "
            "Use for questions about who to ask or who has experience."
        ),
        "required_params": ["service_id"],
        "fn": lambda service_id: (
            {
                "service_id": service_id,
                "experts": fixtures.find_catalog_experts_stub(service_id),
                "graph": fixtures.get_catalog_neighborhood_stub(service_id, 3),
            }
            if get_settings().development_fixtures
            else {
                "service_id": service_id,
                "experts": find_experts(service_id),
                "graph": get_neighborhood(service_id, 3),
            }
        ),
    },
    "get_onboarding_brief": {
        "description": (
            "Complete onboarding: ownership, decisions, experts, "
            "risks, and open incidents for a service."
        ),
        "required_params": ["service_id"],
        "fn": lambda service_id: {
            "overview": (
                fixtures.get_catalog_overview_stub(service_id)
                if get_settings().development_fixtures
                else get_service_overview(service_id)
            ),
            "decisions": (
                fixtures.get_catalog_decisions_stub(service_id)
                if get_settings().development_fixtures
                else get_decisions_for_service(service_id)
            ),
            "experts": (
                fixtures.find_catalog_experts_stub(service_id)
                if get_settings().development_fixtures
                else find_experts(service_id)
            ),
            "blast_radius": (
                fixtures.get_catalog_blast_stub(service_id)
                if get_settings().development_fixtures
                else get_blast_radius(service_id)
            ),
        },
    },
}


def call_tool(tool_name: str, args: dict[str, Any]) -> dict:
    if tool_name not in TOOL_REGISTRY:
        raise ToolNotFoundError(
            f"'{tool_name}' not in approved registry. Valid: {list(TOOL_REGISTRY)}"
        )
    tool = TOOL_REGISTRY[tool_name]
    missing = [p for p in tool["required_params"] if p not in args]
    if missing:
        raise ToolExecutionError(f"Missing params for '{tool_name}': {missing}")
    try:
        return tool["fn"](**{p: args[p] for p in tool["required_params"]})
    except Exception as e:
        raise ToolExecutionError(f"Tool '{tool_name}' failed: {e}") from e


def get_tool_descriptions() -> str:
    return "\n".join(
        f"- {name}: {info['description']}" for name, info in TOOL_REGISTRY.items()
    )
