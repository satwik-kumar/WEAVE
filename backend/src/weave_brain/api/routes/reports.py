from typing import Any

from fastapi import APIRouter, HTTPException, Query

from weave_brain.agent.provider import get_provider
from weave_brain.domain.models import HealthScore
from weave_brain.graph import queries
from weave_brain.services.report_service import (
    build_health_score,
    build_onboarding_brief,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/health-score", response_model=HealthScore)
def health_score() -> HealthScore:
    try:
        return build_health_score()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get("/knowledge-gaps")
def knowledge_gaps() -> dict[str, list[dict[str, Any]]]:
    try:
        raw = queries.get_knowledge_gaps()
        if isinstance(raw, list):
            return {"gaps": raw}
        if isinstance(raw, dict):
            formatted_gaps: list[dict[str, Any]] = []
            for s in raw.get("unowned_services", []):
                formatted_gaps.append(
                    {
                        "entity_id": s.get("id", ""),
                        "entity_title": s.get("title") or s.get("id", ""),
                        "gap_type": "no_owner",
                    }
                )
            for d in raw.get("decisions_missing_rationale", []):
                formatted_gaps.append(
                    {
                        "entity_id": d.get("id", ""),
                        "entity_title": d.get("title") or d.get("id", ""),
                        "gap_type": "missing_rationale",
                    }
                )
            for s in raw.get("undocumented_services", []):
                formatted_gaps.append(
                    {
                        "entity_id": s.get("id", ""),
                        "entity_title": s.get("title") or s.get("id", ""),
                        "gap_type": "undocumented",
                    }
                )
            return {"gaps": formatted_gaps}
        return {"gaps": []}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get("/onboarding")
def onboarding(
    service_id: str = Query(
        ...,
        description="e.g. service:authentication-api",
    ),
) -> dict[str, Any]:
    if not service_id.startswith("service:"):
        raise HTTPException(
            status_code=400, detail="service_id must start with 'service:'"
        )
    try:
        try:
            provider = get_provider()
        except OSError:
            provider = None
        return build_onboarding_brief(service_id, provider)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
