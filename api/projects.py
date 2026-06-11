from fastapi import APIRouter

from utils.storage import list_projects

router = APIRouter()


@router.get("/projects")
def projects_endpoint() -> list[dict]:
    return list_projects()
