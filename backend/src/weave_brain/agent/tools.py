import logging
import os
import re
import socket
from typing import Any

from weave_brain.graph.queries import (
    find_experts,
    get_blast_radius,
    get_decisions_for_service,
    get_neighborhood,
    get_service_overview,
)

__all__ = [
    "TOOL_ALLOWLIST",
    "TOOL_REGISTRY",
    "InvalidEntityIdError",
    "ToolExecutionError",
    "ToolNotFoundError",
    "call_tool",
    "find_experts",
    "get_blast_radius",
    "get_decisions_for_service",
    "get_neighborhood",
    "get_service_overview",
    "get_tool_descriptions",
    "is_valid_canonical_id",
    "validate_canonical_id",
]


class ToolNotFoundError(Exception):
    pass


class ToolExecutionError(Exception):
    pass


class InvalidEntityIdError(ToolExecutionError, ValueError):
    """Raised when an entity ID is malformed or does not conform to the canonical slug pattern."""



# Strict canonical ID pattern: type:slug (lowercase letters, digits, hyphens, slashes, dots)
CANONICAL_ID_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]*:[a-z0-9_\-\/\.:]+$"
)


def is_valid_canonical_id(entity_id: Any) -> bool:
    """Check whether an entity ID strictly adheres to the canonical slug format (type:slug)."""
    if not isinstance(entity_id, str) or not entity_id.strip():
        return False
    if entity_id != entity_id.lower():
        return False
    if any(c in entity_id for c in " \t\r\n;\"'\\`{}()[]<>"):
        return False
    return bool(CANONICAL_ID_PATTERN.match(entity_id))


def validate_canonical_id(entity_id: Any, expected_prefix: str | None = None) -> str:
    """Validate an entity ID argument against canonical slug rules before passing to graph functions."""
    if not isinstance(entity_id, str) or not entity_id.strip():
        raise InvalidEntityIdError(
            f"Malformed ID: expected non-empty string, got {type(entity_id).__name__} ({entity_id!r})"
        )
    if any(c in entity_id for c in " \t\r\n;\"'\\`{}()[]<>"):
        raise InvalidEntityIdError(
            f"Malformed ID '{entity_id}': contains disallowed whitespace or special characters"
        )
    if entity_id != entity_id.lower():
        raise InvalidEntityIdError(
            f"Malformed ID '{entity_id}': canonical IDs must be strictly lowercase"
        )
    if not CANONICAL_ID_PATTERN.match(entity_id):
        raise InvalidEntityIdError(
            f"Malformed ID '{entity_id}': does not match expected canonical slug pattern 'type:slug'"
        )
    if expected_prefix:
        prefix = f"{expected_prefix}:"
        if not entity_id.startswith(prefix):
            raise InvalidEntityIdError(
                f"Malformed ID '{entity_id}': expected entity type prefix '{prefix}'"
            )
    return entity_id



logger = logging.getLogger(__name__)

_falkordb_online_cache: bool | None = None


def _is_falkordb_online() -> bool:
    global _falkordb_online_cache
    if _falkordb_online_cache is not None:
        return _falkordb_online_cache

    if os.getenv("FALKORDB_AVAILABLE") == "1":
        _falkordb_online_cache = True
        return True
    if os.getenv("FALKORDB_AVAILABLE") == "0":
        _falkordb_online_cache = False
        return False

    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    try:
        with socket.create_connection((host, port), timeout=0.05):
            _falkordb_online_cache = True
            return True
    except OSError:
        _falkordb_online_cache = False
        return False


def _safe_service_overview(service_id: str) -> dict[str, Any]:
    validate_canonical_id(service_id, expected_prefix="service")
    res = None
    if _is_falkordb_online():
        try:
            res = get_service_overview(service_id)
        except Exception as e:  # noqa: BLE001
            logger.debug("Offline fallback for get_service_overview (%s)", e)
    if res is None:
        from weave_brain.graph.fixtures import get_service_overview_stub

        overview_dict = dict(get_service_overview_stub(service_id))
    else:
        overview_dict = dict(res)

    if "experts" not in overview_dict:
        overview_dict["experts"] = _safe_find_experts(service_id).get("experts", [])

    return overview_dict


def _safe_blast_radius(service_id: str) -> dict[str, Any]:
    validate_canonical_id(service_id, expected_prefix="service")
    if _is_falkordb_online():
        try:
            res = get_blast_radius(service_id)
            if res is not None:
                return res
        except Exception as e:  # noqa: BLE001
            logger.debug("Offline fallback for get_blast_radius (%s)", e)
    from weave_brain.graph.fixtures import get_blast_radius_stub

    return get_blast_radius_stub(service_id)


def _safe_decisions_for_service(service_id: str) -> dict[str, Any]:
    validate_canonical_id(service_id, expected_prefix="service")
    if _is_falkordb_online():
        try:
            res = get_decisions_for_service(service_id)
            if res is not None:
                return res
        except Exception as e:  # noqa: BLE001
            logger.debug("Offline fallback for get_decisions_for_service (%s)", e)
    from weave_brain.graph.fixtures import get_decisions_for_service_stub

    return get_decisions_for_service_stub(service_id)


def _safe_find_experts(service_id: str) -> dict[str, Any]:
    validate_canonical_id(service_id, expected_prefix="service")
    experts_list: list[dict[str, Any]] = []
    if _is_falkordb_online():
        try:
            res = find_experts(service_id)
            if isinstance(res, list) and len(res) > 0:
                experts_list = res
        except Exception as e:  # noqa: BLE001
            logger.debug("Offline fallback for find_experts (%s)", e)
    if not experts_list:
        from weave_brain.graph.fixtures import find_experts_stub

        experts_list = find_experts_stub(service_id)
    return {"experts": experts_list}


def _safe_onboarding_brief(service_id: str) -> dict[str, Any]:
    validate_canonical_id(service_id, expected_prefix="service")
    overview = _safe_service_overview(service_id)
    decisions = _safe_decisions_for_service(service_id)
    experts = _safe_find_experts(service_id)
    blast_radius = _safe_blast_radius(service_id)
    return {
        "service_id": service_id,
        "overview": overview,
        "decisions": decisions,
        "experts": experts,
        "blast_radius": blast_radius,
    }


TOOL_REGISTRY: dict[str, dict] = {
    "get_service_overview": {
        "description": (
            "Ownership, team members, repos, dependencies, "
            "and linked decisions for a service."
        ),
        "required_params": ["service_id"],
        "fn": lambda service_id: _safe_service_overview(service_id),
    },
    "get_blast_radius": {
        "description": (
            "All services that depend on this service with hop depth "
            "and owning teams. Use for impact and breakage questions."
        ),
        "required_params": ["service_id"],
        "fn": lambda service_id: _safe_blast_radius(service_id),
    },
    "get_decisions_for_service": {
        "description": (
            "Architecture decisions, their rationale, and motivating incidents."
        ),
        "required_params": ["service_id"],
        "fn": lambda service_id: _safe_decisions_for_service(service_id),
    },
    "find_experts": {
        "description": (
            "People who worked on projects using this service. "
            "Use for questions about who to ask or who has experience."
        ),
        "required_params": ["service_id"],
        "fn": lambda service_id: _safe_find_experts(service_id),
    },
    "get_onboarding_brief": {
        "description": (
            "Complete onboarding: ownership, decisions, experts, "
            "risks, and open incidents for a service."
        ),
        "required_params": ["service_id"],
        "fn": lambda service_id: _safe_onboarding_brief(service_id),
    },
}

TOOL_ALLOWLIST: set[str] = set(TOOL_REGISTRY.keys())


def call_tool(tool_name: str, args: dict[str, Any]) -> dict:
    if tool_name not in TOOL_ALLOWLIST or tool_name not in TOOL_REGISTRY:
        raise ToolNotFoundError(
            f"Tool '{tool_name}' rejected: not in approved tool allowlist. Allowed: {sorted(TOOL_ALLOWLIST)}"
        )
    tool = TOOL_REGISTRY[tool_name]
    missing = [p for p in tool["required_params"] if p not in args]
    if missing:
        raise ToolExecutionError(f"Missing params for '{tool_name}': {missing}")

    # Validate every ID argument against expected slug pattern before it reaches graph functions
    for param in tool["required_params"]:
        val = args[param]
        if param == "service_id":
            validate_canonical_id(val, expected_prefix="service")
        elif param == "id" or param.endswith("_id"):
            validate_canonical_id(val)

    try:
        return tool["fn"](**{p: args[p] for p in tool["required_params"]})
    except (ToolExecutionError, ToolNotFoundError):
        raise
    except Exception as e:
        raise ToolExecutionError(f"Tool '{tool_name}' failed: {e}") from e


def get_tool_descriptions() -> str:
    return "\n".join(
        f"- {name}: {info['description']}" for name, info in TOOL_REGISTRY.items()
    )

