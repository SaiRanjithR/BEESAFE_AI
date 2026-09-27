import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.auth import verify_api_key, require_institution
from app.db.database import get_db
from app.db.models import ThreatIndicator, RiskAssessment, AuditLog
from app.schemas import InstitutionIndicatorOut, BlockIndicatorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/indicators", tags=["Indicators"])


@router.get("", response_model=List[InstitutionIndicatorOut])
def list_indicators(
    indicator_type: Optional[str] = Query(None, alias="type", description="Filter by indicator type"),
    indicator_status: Optional[str] = Query(None, alias="status", description="Filter by status (pending, blocked)"),
    min_risk: Optional[int] = Query(None, ge=0, le=100, description="Minimum risk score threshold"),
    correlated_only: Optional[bool] = Query(None, description="If True, only return indicators observed in > 1 conversation"),
    sort_by: str = Query("risk_desc", description="Sort order: risk_desc, risk_asc, correlated_desc, created_desc, created_asc"),
    _auth: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    List extracted threat indicators for financial institutions.
    Includes multi-conversation correlation count (distinct conversations where the value appeared).
    Role boundary enforcement: strictly excludes conversation transcripts, messages,
    and honeypot persona details. Only returns indicator entities and associated risk scoring.
    """
    # Correlation subquery: count distinct conversations per indicator value
    corr_subq = (
        db.query(
            ThreatIndicator.value,
            func.count(func.distinct(ThreatIndicator.conversation_id)).label("conversation_count"),
        )
        .group_by(ThreatIndicator.value)
        .subquery()
    )

    # Outer join with RiskAssessment to include score/evidence and correlation count
    query = (
        db.query(ThreatIndicator, RiskAssessment, corr_subq.c.conversation_count)
        .outerjoin(RiskAssessment, ThreatIndicator.conversation_id == RiskAssessment.conversation_id)
        .outerjoin(corr_subq, ThreatIndicator.value == corr_subq.c.value)
    )

    if indicator_type:
        query = query.filter(ThreatIndicator.indicator_type == indicator_type)

    if indicator_status:
        query = query.filter(ThreatIndicator.status == indicator_status)

    if min_risk is not None:
        query = query.filter(RiskAssessment.risk_score >= min_risk)

    if correlated_only:
        query = query.filter(corr_subq.c.conversation_count > 1)

    if sort_by == "risk_asc":
        query = query.order_by(RiskAssessment.risk_score.asc().nullslast(), ThreatIndicator.created_at.desc())
    elif sort_by == "correlated_desc":
        query = query.order_by(corr_subq.c.conversation_count.desc(), RiskAssessment.risk_score.desc().nullslast())
    elif sort_by == "created_desc":
        query = query.order_by(ThreatIndicator.created_at.desc())
    elif sort_by == "created_asc":
        query = query.order_by(ThreatIndicator.created_at.asc())
    else:  # default risk_desc
        query = query.order_by(RiskAssessment.risk_score.desc().nullslast(), ThreatIndicator.created_at.desc())

    results = query.all()

    items = []
    for ind, risk, count in results:
        items.append(
            InstitutionIndicatorOut(
                id=ind.id,
                conversation_id=ind.conversation_id,
                indicator_type=ind.indicator_type,
                value=ind.value,
                status=ind.status,
                known_bad=ind.known_bad,
                domain_age_days=ind.domain_age_days,
                created_at=ind.created_at,
                risk_score=risk.risk_score if risk else None,
                risk_classification=risk.classification if risk else None,
                risk_reasons=risk.reasons if risk else None,
                conversation_count=count if count is not None else 1,
            )
        )

    return items


@router.post("/{indicator_id}/block", response_model=BlockIndicatorResponse)
def block_indicator(
    indicator_id: uuid.UUID,
    _auth: str = Depends(require_institution),
    db: Session = Depends(get_db),
):
    """
    Marks an indicator as 'blocked'.
    Idempotent: if already blocked, returns success without creating a duplicate audit log entry.
    Logs human action in audit_logs.
    """
    indicator = db.query(ThreatIndicator).filter(ThreatIndicator.id == indicator_id).first()
    if not indicator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator '{indicator_id}' not found.",
        )

    if indicator.status == "blocked":
        # Idempotent: already blocked, do not duplicate audit log entry
        logger.info("Indicator %s is already blocked; no-op", indicator_id)
        return BlockIndicatorResponse(
            status="already_blocked",
            indicator_id=indicator.id,
            current_status="blocked",
        )

    indicator.status = "blocked"

    audit_entry = AuditLog(
        conversation_id=indicator.conversation_id,
        actor="institution_viewer",
        action="blocked_indicator",
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(indicator)

    logger.info("Indicator %s successfully blocked by institution_viewer", indicator_id)
    return BlockIndicatorResponse(
        status="blocked",
        indicator_id=indicator.id,
        current_status="blocked",
    )
