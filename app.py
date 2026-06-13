import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.agents import router as agents_router
from api.analyze import router as analyze_router
from api.dispatch import router as dispatch_router
from api.folderpicker import router as folderpicker_router
from api.generate import router as generate_router
from api.projects import router as projects_router
from api.usage import router as usage_router

app = FastAPI(title="Agent Orchestrator")

app.include_router(agents_router)
app.include_router(analyze_router)
app.include_router(dispatch_router)
app.include_router(folderpicker_router)
app.include_router(generate_router)
app.include_router(projects_router)
app.include_router(usage_router)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse("frontend/index.html")


@app.get("/preview")
def preview() -> FileResponse:
    return FileResponse("frontend/preview.html")


@app.get("/generating")
def generating() -> FileResponse:
    return FileResponse("frontend/generating.html")


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
