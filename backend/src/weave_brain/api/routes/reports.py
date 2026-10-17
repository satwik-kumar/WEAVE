"""Report endpoints, registered once using their full canonical /api paths."""

from fastapi import APIRouter, Request

from weave_brain.domain.models import HealthReport, KnowledgeGaps, OnboardingBrief
from weave_brain.services.graph_service import Retrieval
from weave_brain.services.report_service import ReportService

router = APIRouter(tags=["reports"])


def reports(request: Request) -> ReportService:
    return ReportService(request.app.state.graph_service)


@router.get("/api/health-score", response_model=HealthReport)
@router.get("/api/reports/health-score", response_model=HealthReport)
def health(request: Request):
    return reports(request).health()


@router.get("/api/reports/knowledge-gaps", response_model=KnowledgeGaps)
def knowledge_gaps(request: Request):
    return reports(request).gaps()


@router.get("/api/reports/onboarding/{service_id}", response_model=OnboardingBrief)
def onboarding(service_id: str, request: Request):
    from weave_brain.api.main import canonical

    return reports(request).onboarding(canonical(service_id, True))


@router.get("/api/reports/onboarding", response_model=OnboardingBrief)
def onboarding_query(service_id: str, request: Request):
    return onboarding(service_id, request)


@router.get("/api/services/{service_id}/decisions", response_model=Retrieval)
def decisions(service_id: str, request: Request):
    from weave_brain.api.main import canonical

    return reports(request).decisions(canonical(service_id, True))
