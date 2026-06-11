from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.folderpicker import FolderPickerTimeout, pick_folder

router = APIRouter()


@router.get("/pick-folder")
def pick_folder_endpoint() -> JSONResponse:
    try:
        path = pick_folder()
    except FolderPickerTimeout:
        return JSONResponse(content={"path": ""}, status_code=408)
    except Exception as e:
        return JSONResponse(content={"path": "", "error": str(e)}, status_code=500)

    resp = JSONResponse(content={"path": path})
    resp.headers["Cache-Control"] = "no-store"
    return resp
