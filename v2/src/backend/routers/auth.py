"""Auth endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from shared.common.auth import AuthenticatedUser, get_authenticated_user
from shared.config.config_helper import ConfigHelper

router = APIRouter()


@router.get("/checkauth")
async def check_auth(user: AuthenticatedUser = Depends(get_authenticated_user)):
    return {
        "authenticated": bool(user.user_principal_id),
        "user_principal_id": user.user_principal_id,
        "user_name": user.user_name,
        "auth_provider": user.auth_provider,
    }


@router.get("/assistanttype")
async def get_assistant_type(req: Request):
    config = ConfigHelper.get_active_config_or_default()
    return {"assistant_type": config.prompts.conversational_flow}
