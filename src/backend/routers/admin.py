"""Admin endpoints: config CRUD, documents, upload SAS."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/settings")
async def get_settings():
    # TODO: Phase 2 — return Function App URL + key
    return {"function_url": "", "function_key": ""}


@router.post("/upload-sas")
async def get_upload_sas():
    # TODO: Phase 2 — generate SAS token for direct blob upload
    return {"sas_url": ""}


@router.get("/documents")
async def list_documents():
    # TODO: Phase 2
    return {"documents": []}


@router.delete("/documents")
async def delete_documents():
    # TODO: Phase 2
    return {"success": True}


@router.get("/config")
async def get_config():
    # TODO: Phase 2 — load active.json from blob
    return {}


@router.put("/config")
async def update_config():
    # TODO: Phase 2 — save config to blob
    return {"success": True}
