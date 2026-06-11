from fastapi import APIRouter
from pydantic import BaseModel

from utils.agents_store import list_agents, set_pinned

router = APIRouter()


class PinRequest(BaseModel):
    pinned: bool


@router.get("/agents")
def agents_endpoint() -> list[dict]:
    return list_agents()


@router.post("/agents/{name}/pin")
def pin_agent_endpoint(name: str, req: PinRequest) -> dict:
    set_pinned(name, req.pinned)
    return {"ok": True, "name": name, "pinned": req.pinned}
