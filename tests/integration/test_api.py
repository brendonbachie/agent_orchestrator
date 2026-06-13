import json
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from utils.claude import ClaudeError

_PROPOSTA = {
    "claude_md": "# Test Project\n",
    "agentes": [{"name": "test-writer", "source": "biblioteca", "conteudo": None}],
    "hooks": [],
    "primeiro_prompt": "Start here",
}

_GENERATE_PAYLOAD = {
    "pasta": "/tmp/test-proj",
    "claude_md": "# proj",
    "agentes": [],
    "hooks": [],
    "primeiro_prompt": "Go!",
}


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ── GET / ────────────────────────────────────────────────────────────────────

async def test_index_returns_html(client):
    res = await client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]


# ── GET /preview ─────────────────────────────────────────────────────────────

async def test_preview_returns_html(client):
    res = await client.get("/preview")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]


# ── GET /generating ──────────────────────────────────────────────────────────

async def test_generating_returns_html(client):
    res = await client.get("/generating")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]


# ── POST /analyze ─────────────────────────────────────────────────────────────

async def test_analyze_success(client):
    with patch("api.analyze.analyze", return_value=_PROPOSTA):
        res = await client.post(
            "/analyze", json={"descricao": "Uma API simples", "pasta": "/tmp/p"}
        )
    assert res.status_code == 200
    data = res.json()
    assert "claude_md" in data
    assert "agentes" in data
    assert "hooks" in data
    assert "primeiro_prompt" in data


async def test_analyze_claude_error_returns_502(client):
    with patch("api.analyze.analyze", side_effect=ClaudeError("claude not found")):
        res = await client.post(
            "/analyze", json={"descricao": "x", "pasta": "/tmp/p"}
        )
    assert res.status_code == 502
    assert "claude not found" in res.json()["detail"]


async def test_analyze_missing_fields_returns_422(client):
    res = await client.post("/analyze", json={"descricao": "no pasta"})
    assert res.status_code == 422


# ── POST /generate ────────────────────────────────────────────────────────────

async def test_generate_success(client):
    with (
        patch("core.builder.build", return_value={"CLAUDE.md": "# x"}),
        patch("core.writer.check_conflicts", return_value=[]),
        patch("core.writer.write"),
        patch("core.launcher.launch"),
        patch("utils.storage.save_project"),
    ):
        res = await client.post("/generate", json=_GENERATE_PAYLOAD)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["pasta"] == "/tmp/test-proj"
    assert "CLAUDE.md" in data["files"]
    assert data["launch_error"] is None


async def test_generate_conflict_returns_409(client):
    with (
        patch("core.builder.build", return_value={"CLAUDE.md": "# x"}),
        patch("core.writer.check_conflicts", return_value=["CLAUDE.md", ".claude/agents/a.md"]),
        patch("core.writer.write") as mock_write,
        patch("core.launcher.launch") as mock_launch,
        patch("utils.storage.save_project"),
    ):
        res = await client.post("/generate", json=_GENERATE_PAYLOAD)
    assert res.status_code == 409
    assert res.json()["detail"] == {"conflitos": ["CLAUDE.md", ".claude/agents/a.md"]}
    mock_write.assert_not_called()
    mock_launch.assert_not_called()


async def test_generate_sobrescrever_true_ignores_conflicts(client):
    payload = {**_GENERATE_PAYLOAD, "sobrescrever": True}
    with (
        patch("core.builder.build", return_value={"CLAUDE.md": "# x"}),
        patch("core.writer.check_conflicts", return_value=["CLAUDE.md"]) as mock_check,
        patch("core.writer.write") as mock_write,
        patch("core.launcher.launch"),
        patch("utils.storage.save_project"),
    ):
        res = await client.post("/generate", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True
    mock_check.assert_not_called()
    mock_write.assert_called_once()


async def test_generate_write_error_returns_500(client):
    with (
        patch("core.builder.build", return_value={}),
        patch("core.writer.check_conflicts", return_value=[]),
        patch("core.writer.write", side_effect=OSError("disk full")),
    ):
        res = await client.post("/generate", json=_GENERATE_PAYLOAD)
    assert res.status_code == 500
    assert "disk full" in res.json()["detail"]


async def test_generate_launch_error_still_returns_ok(client):
    with (
        patch("core.builder.build", return_value={"CLAUDE.md": "x"}),
        patch("core.writer.check_conflicts", return_value=[]),
        patch("core.writer.write"),
        patch("core.launcher.launch", side_effect=FileNotFoundError("claude not found")),
        patch("utils.storage.save_project"),
    ):
        res = await client.post("/generate", json=_GENERATE_PAYLOAD)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["launch_error"] is not None


async def test_generate_missing_fields_returns_422(client):
    res = await client.post("/generate", json={"pasta": "/tmp/p"})
    assert res.status_code == 422


# ── GET /projects ─────────────────────────────────────────────────────────────

async def test_projects_returns_list(client):
    projects = [
        {
            "pasta": "/proj/a",
            "files": ["CLAUDE.md"],
            "primeiro_prompt": "Go",
            "criado_em": "2025-01-01T00:00:00+00:00",
        }
    ]
    with patch("api.projects.list_projects", return_value=projects):
        res = await client.get("/projects")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["pasta"] == "/proj/a"


async def test_projects_empty_list(client):
    with patch("api.projects.list_projects", return_value=[]):
        res = await client.get("/projects")
    assert res.status_code == 200
    assert res.json() == []


# ── GET /usage ────────────────────────────────────────────────────────────────


async def test_usage_aggregates_session(client):
    fake = json.dumps(
        {"message": {"usage": {
            "input_tokens": 10, "cache_creation_input_tokens": 100,
            "cache_read_input_tokens": 1000, "output_tokens": 5,
        }}}
    )
    with patch("api.usage.read_session_jsonl", return_value=fake):
        res = await client.get("/usage", params={"pasta": "C:\\proj\\x"})
    assert res.status_code == 200
    data = res.json()
    assert data["encontrado"] is True
    assert data["total"] == 1115
    assert data["cache_read"] == 1000


async def test_usage_no_session_found(client):
    with patch("api.usage.read_session_jsonl", return_value=""):
        res = await client.get("/usage", params={"pasta": "C:\\proj\\x"})
    assert res.status_code == 200
    assert res.json()["encontrado"] is False


async def test_usage_missing_pasta_returns_422(client):
    res = await client.get("/usage")
    assert res.status_code == 422


# ── POST /dispatch ────────────────────────────────────────────────────────────


async def test_dispatch_streams_tasks_and_summary(client):
    def fake_run_task(prompt, model, cwd):
        return {"ok": True, "usage": {}, "cost_usd": 0.5}

    plano = [
        {"ordem": 1, "task": "fundação", "modelo": "opus"},
        {"ordem": 2, "task": "folha", "modelo": "sonnet", "depende_de": [1]},
    ]
    with (
        patch("api.dispatch.run_task", fake_run_task),
        patch("api.dispatch.run_pytest", lambda pasta: True),
    ):
        res = await client.post("/dispatch", json={"pasta": "/p", "plano": plano})
    assert res.status_code == 200
    linhas = [json.loads(x) for x in res.text.splitlines() if x.strip()]
    tasks = [e for e in linhas if e.get("tipo") == "task"]
    resumo = next(e for e in linhas if e.get("tipo") == "resumo")
    assert [t["ordem"] for t in tasks] == [1, 2]  # ordem topológica, ao vivo
    assert tasks[0]["testes_ok"] is True  # gate de testes rodou
    assert resumo["custo_usd_total"] == 1.0


async def test_dispatch_empty_plan_returns_400(client):
    res = await client.post("/dispatch", json={"pasta": "/p", "plano": []})
    assert res.status_code == 400
