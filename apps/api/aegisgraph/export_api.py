"""A bounded case export; verification never accepts public uploads."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from . import config
from .db import get_db

router = APIRouter(prefix="/api", tags=["evidence export"])
CaseId = Annotated[str, Path(pattern=r"^INC-[A-Za-z0-9-]+$", max_length=80)]


@router.get("/incidents/{incident_id}/export")
def export(incident_id: CaseId, request: Request, db: Session = Depends(get_db)):
    if request.query_params:
        raise HTTPException(422, "Export query parameters are not supported")
    from .evidence_export import export_incident

    return export_incident(db, incident_id, public_demo=config.settings.public_demo)
