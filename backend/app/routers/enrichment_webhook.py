import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.db.database import get_db
from app.db.models import ThreatIndicator
from app.schemas import EnrichmentCallbackRequest, EnrichmentCallbackResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Enrichment Webhook"])


@router.post("/enrichment-result", response_model=EnrichmentCallbackResponse, status_code=status.HTTP_200_OK)
def enrichment_callback(
    payload: EnrichmentCallbackRequest,
    db: Session = Depends(get_db),
    _auth: str = Depends(verify_api_key),
):
    """
    Receives callback from n8n (or external enrichment pipelines) with URL WHOIS and blocklist findings.
    Updates the target ThreatIndicator record with 'known_bad' and 'domain_age_days'.
    """
    indicator = db.query(ThreatIndicator).filter(ThreatIndicator.id == payload.indicator_id).first()
    if not indicator:
        logger.warning(f"Enrichment callback received for unknown indicator: {payload.indicator_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Threat indicator '{payload.indicator_id}' not found.",
        )

    indicator.known_bad = payload.known_bad
    indicator.domain_age_days = payload.domain_age_days
    db.commit()
    db.refresh(indicator)

    logger.info(
        f"Updated indicator {indicator.id} via enrichment callback: "
        f"known_bad={indicator.known_bad}, domain_age_days={indicator.domain_age_days}"
    )

    return EnrichmentCallbackResponse(
        status="success",
        indicator_id=indicator.id,
        known_bad=indicator.known_bad,
        domain_age_days=indicator.domain_age_days,
    )
