import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.analyzer import analyze
from utils.claude import ClaudeError

router = APIRouter()


class AnalyzeRequest(BaseModel):
    descricao: str
    pasta: str


@router.post("/analyze")
async def analyze_endpoint(req: AnalyzeRequest) -> dict:
    try:
        result = await asyncio.to_thread(analyze, req.descricao)
        return result
    except ClaudeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
