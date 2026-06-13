import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core import builder, launcher, writer
from utils import storage
from utils.agents_store import save_agents_from_files
from utils.claude_sessions import to_wsl_path

router = APIRouter()


class GenerateRequest(BaseModel):
    pasta: str
    claude_md: str
    agentes: list[dict]
    hooks: list[dict]
    primeiro_prompt: str
    plano: list[dict] = []
    skills: list[str] = []
    sobrescrever: bool = False


@router.post("/generate")
async def generate_endpoint(req: GenerateRequest) -> dict:
    # Keep original path for file writing (Windows Python understands Windows paths)
    pasta_write = req.pasta
    # Convert to WSL path only for the launcher (runs inside WSL)
    pasta_wsl = to_wsl_path(req.pasta)
    try:
        files = builder.build(
            req.claude_md, req.agentes, req.hooks, req.primeiro_prompt, req.plano
        )
        if not req.sobrescrever:
            conflitos = await asyncio.to_thread(writer.check_conflicts, files, pasta_write)
            if conflitos:
                raise HTTPException(status_code=409, detail={"conflitos": conflitos})
        await asyncio.to_thread(writer.write, files, pasta_write)
        await asyncio.to_thread(save_agents_from_files, files)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    file_list = list(files.keys())
    await asyncio.to_thread(storage.save_project, pasta_write, file_list, req.primeiro_prompt)

    launch_error: str | None = None
    try:
        launcher.launch(pasta_wsl)
    except Exception as e:
        launch_error = str(e)

    return {
        "ok": True,
        "pasta": req.pasta,
        "files": file_list,
        "launch_error": launch_error,
    }
