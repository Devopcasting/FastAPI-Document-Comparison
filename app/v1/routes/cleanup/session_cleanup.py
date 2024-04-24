import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
import shutil

router = APIRouter()

IMAGE_WORKSPACE = os.path.abspath(os.path.join("app", "v1", "static", "image"))
EXCEL_WORKSPACE = os.path.abspath(os.path.join("app", "v1", "static", "excel"))

class SessionID(BaseModel):
    session_id: str

@router.post("/clean_session")
async def cleanup(sessionid: SessionID):
    sessionId = sessionid.session_id
    image_sesssion_id_path = os.path.join(IMAGE_WORKSPACE, sessionId)
    excel_session_id_path = os.path.join(EXCEL_WORKSPACE, sessionId)

    try:
        if os.path.exists(image_sesssion_id_path):
            shutil.rmtree(image_sesssion_id_path)

        if os.path.exists(excel_session_id_path):
            shutil.rmtree(excel_session_id_path)
    
        data = {"result": f"Session ID {sessionId} cleanup sucecssfully"}
        return JSONResponse(content=data, status_code=200)
    except Exception as e:
        data = {"result": f"Session ID {sessionId} not available for cleanup"}
        return JSONResponse(content=data, status_code=404)

