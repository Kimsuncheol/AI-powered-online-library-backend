from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.models.member import Member
from app.security.session import require_session

router = APIRouter(prefix="/activity", tags=["activity"])


@router.post("/heartbeat", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def heartbeat(_: Member = Depends(require_session)) -> Response:
    """Touch the session to keep it active during long-lived interactions."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)
