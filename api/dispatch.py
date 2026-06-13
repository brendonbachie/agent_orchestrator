import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.dispatcher import ordenar, prompt_da_task
from utils.claude import run_task
from utils.verify import run_pytest

router = APIRouter()


class DispatchRequest(BaseModel):
    pasta: str
    plano: list[dict]
    skills: list[str] = []
    verificar: bool = True


@router.post("/dispatch")
async def dispatch_endpoint(req: DispatchRequest) -> StreamingResponse:
    if not req.plano:
        raise HTTPException(status_code=400, detail="plano vazio")

    async def stream() -> AsyncIterator[str]:
        feitas: list[dict] = []
        total = 0.0
        for task in ordenar(req.plano):
            modelo = task.get("modelo") or "sonnet"
            try:
                res = await asyncio.to_thread(
                    run_task, prompt_da_task(task, feitas), modelo, req.pasta
                )
            except Exception as e:  # uma task ruim não derruba o stream
                res = {"ok": False, "erro": str(e)}

            entrada: dict = {
                "tipo": "task",
                "ordem": task.get("ordem"),
                "task": task.get("task", ""),
                "modelo": modelo,
                "agente": task.get("agente"),
            }
            entrada.update(res)
            if req.verificar and res.get("ok"):
                entrada["testes_ok"] = await asyncio.to_thread(run_pytest, req.pasta)
            custo = res.get("cost_usd")
            total += float(custo) if isinstance(custo, (int, float)) else 0.0
            feitas.append(task)
            yield json.dumps(entrada, ensure_ascii=False) + "\n"

        yield json.dumps(
            {"tipo": "resumo", "custo_usd_total": round(total, 4)}, ensure_ascii=False
        ) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")
