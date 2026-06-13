import asyncio

from fastapi import APIRouter

from core.usage import aggregate
from utils.claude_sessions import read_session_jsonl, to_wsl_path

router = APIRouter()


@router.get("/usage")
async def usage_endpoint(pasta: str) -> dict[str, object]:
    pasta_wsl = to_wsl_path(pasta)
    text = await asyncio.to_thread(read_session_jsonl, pasta_wsl)
    return aggregate(text)
