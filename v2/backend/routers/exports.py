# -- /api/exports - list and download export files. --

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from services.export_service import list_exports, EXPORTS_DIR

router = APIRouter()

@router.get("/")
async def list_export_files():
    return list_exports()

@router.get("/download/{filename}")
async def download_export(filename: str):
    # Security: prevent path traversal
    path = (EXPORTS_DIR / filename).resolve()
    if not str(path).startswith(str(EXPORTS_DIR.resolve())):
        raise HTTPException(400, "Invalid filename")
    if not path.exists():
        raise HTTPException(404, "File not found")

    media_types = {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".csv": "text/csv",
        ".json": "application/json",
    }
    media_type = media_types.get(path.suffix, "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=path.name)

@router.delete("/{filename}")
async def delete_export(filename: str):
    path = (EXPORTS_DIR / filename).resolve()
    if not str(path).startswith(str(EXPORTS_DIR.resolve())):
        raise HTTPException(400, "Invalid filename")
    if not path.exists():
        raise HTTPException(404, "File not found")
    os.remove(path)
    return {"deleted": True}
