"""Problem-report endpoints (problem_reports_bridge.md B-8/B-11).

- ``POST /reports`` — the UI report button: free text + page context + browser
  evidence in; the backend assembles Tiers A+B, redacts, packages the §5 envelope
  and files it (or spools offline). Gated by ``system.json reports.enabled`` +
  the B-6 rate limit.
- ``GET /reports/evidence`` — the B-11 read seam: the same bundle-shaped,
  redacted evidence WITHOUT filing. The envelope shape is the bridge's contract
  surface (the voice collector folds it into voice bundles); always available.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from locveil_bridge.domain.reports.models import EvidenceEnvelope, ReportFilingResult
from locveil_bridge.domain.reports.service import RateLimited, ReportService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])

report_service: Optional[ReportService] = None


def initialize(service: ReportService) -> None:
    global report_service
    report_service = service


class ReportRequest(BaseModel):
    free_text: str = Field(min_length=1, description="The user's problem description, verbatim")
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Page context: route, entity_id — anchors the evidence scoping (B-1)")
    ui_evidence: Optional[Dict[str, Any]] = Field(
        default=None, description="Browser-side evidence (B-4): action log, console/API rings, SSE health, app context")


class ReportResponse(BaseModel):
    success: bool
    report_id: str
    spooled: bool = Field(description="True = delivery failed, the report is spooled and will retry (B-7)")
    url: Optional[str] = Field(default=None, description="Ticket URL when filed immediately")


@router.post("/reports", response_model=ReportResponse)
async def file_problem_report(request: ReportRequest) -> ReportResponse:
    """File a problem report: collect evidence, package the envelope, deliver (or spool)."""
    if report_service is None:
        raise HTTPException(status_code=503, detail="Report service not initialized")
    if not report_service.settings.enabled:
        raise HTTPException(status_code=503, detail="Problem reporting is not enabled on this bridge")
    try:
        result: ReportFilingResult = await report_service.file_report(
            request.free_text, request.context, request.ui_evidence
        )
    except RateLimited as e:
        raise HTTPException(status_code=429, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return ReportResponse(
        success=True, report_id=result.report_id, spooled=result.spooled, url=result.url
    )


@router.get("/reports/evidence", response_model=EvidenceEnvelope)
async def get_report_evidence(
    entity_id: Optional[str] = Query(default=None, description="Anchor entity for B-1 scoping (optional)"),
) -> EvidenceEnvelope:
    """The bundle-shaped, redacted evidence — no ticket filed (B-11 read seam)."""
    if report_service is None:
        raise HTTPException(status_code=503, detail="Report service not initialized")
    return await report_service.collect_evidence(entity_id)
