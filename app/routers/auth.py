from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.models.member import Member
from app.schemas.member import MemberCreate, MemberLogin, MemberOut, member_to_schema
from app.services.auth_service import AuthResult, AuthService, get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_member(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    service: AuthService = Depends(get_auth_service),
) -> Member:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "Authentication required."},
        )
    return service.get_current_member(credentials.credentials)


class SignInResponse(BaseModel):
    member: MemberOut
    access_token: str = Field(alias="accessToken")
    refresh_token: Optional[str] = Field(default=None, alias="refreshToken")

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
def signin(payload: MemberLogin, service: AuthService = Depends(get_auth_service)) -> SignInResponse:
    """Authenticate a member and return tokens."""
    result: AuthResult = service.authenticate(email=payload.email, password=payload.password)
    return SignInResponse(
        member=result.member,
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
    )


@router.get("/me", response_model=MemberOut)
def read_current_member(current_member: Member = Depends(get_current_member)) -> MemberOut:
    """Return profile information for the authenticated member."""
    return member_to_schema(current_member)


@router.post("/signout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def signout() -> Response:
    """Stateless sign-out endpoint placeholder."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)
