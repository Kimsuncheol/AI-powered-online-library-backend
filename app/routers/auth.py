from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.models.member import Member
from app.schemas.member import MemberCreate, MemberLogin, MemberOut, member_to_schema
from app.core.settings import SessionSettings, get_session_settings
from app.security.session import require_session
from app.services.auth_service import AuthService, get_auth_service
from app.services.session_service import SessionService, get_session_service

router = APIRouter(prefix="/auth", tags=["auth"])


def get_current_member(member: Member = Depends(require_session)) -> Member:
    return member


class SignInResponse(BaseModel):
    member: MemberOut

    model_config = {"populate_by_name": True}


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=MemberOut,
)
def signup(payload: MemberCreate, service: AuthService = Depends(get_auth_service)) -> MemberOut:
    """Register a new member account."""
    return service.register_member(payload)


@router.post(
    "/signin",
    status_code=status.HTTP_200_OK,
    response_model=SignInResponse,
)
def signin(
    payload: MemberLogin,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    session_service: SessionService = Depends(get_session_service),
    settings: SessionSettings = Depends(get_session_settings),
) -> SignInResponse:
    """Authenticate a member, create a session, and return profile data."""
    member = service.authenticate(email=payload.email, password=payload.password)
    session = session_service.create_session(
        member=member,
        user_agent=request.headers.get("user-agent"),
        ip_addr=request.client.host if request.client else None,
    )
    response.set_cookie(
        key=settings.cookie_name,
        value=session.id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.cookie_max_age_seconds,
        domain=settings.cookie_domain,
        path=settings.cookie_path,
    )
    return SignInResponse(member=member_to_schema(member))


@router.get("/me", response_model=MemberOut)
def read_current_member(current_member: Member = Depends(get_current_member)) -> MemberOut:
    """Return profile information for the authenticated member."""
    return member_to_schema(current_member)


@router.post("/signout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def signout(
    request: Request,
    response: Response,
    session_service: SessionService = Depends(get_session_service),
    settings: SessionSettings = Depends(get_session_settings),
    current_member: Member = Depends(get_current_member),
) -> Response:
    """Revoke the active session and clear the session cookie."""
    session_id = request.cookies.get(settings.cookie_name)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "no_session_cookie", "message": "Session cookie is missing."},
        )

    session_service.revoke_session(session_id)
    _ = current_member  # dependency ensures an active session existed
    response.delete_cookie(
        key=settings.cookie_name,
        domain=settings.cookie_domain,
        path=settings.cookie_path,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
