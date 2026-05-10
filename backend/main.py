from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import get_settings
from .database import init_db
from .schemas import ChatMessageIn, DecisionUpdate, RagQuery
from .services import (
    build_rag_index,
    chat_history,
    chat_message,
    config_status,
    delete_textbook,
    extract_knowledge,
    game_level,
    game_skill_tree,
    generate_report,
    get_graph,
    get_merged_graph,
    get_textbook,
    handle_upload,
    initialize_app_data,
    integration_stats,
    list_decisions,
    list_textbooks,
    rag_query,
    rag_status,
    sync_textbook_to_dify,
    update_decision,
    ensure_merged_graph,
)


class BasePathMiddleware:
    def __init__(self, app: ASGIApp, base_path: str) -> None:
        self.app = app
        self.base_path = base_path.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"} or not self.base_path:
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path == self.base_path:
            scope = {**scope, "path": "/", "root_path": self.base_path}
        elif path.startswith(self.base_path + "/"):
            scope = {**scope, "path": path[len(self.base_path) :] or "/", "root_path": self.base_path}
        await self.app(scope, receive, send)


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()
    app = FastAPI(title="学科知识整合智能体", version="1.0.0")
    if settings.app_base_path:
        app.add_middleware(BasePathMiddleware, base_path=settings.app_base_path)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins + ["http://localhost:7860", "http://127.0.0.1:7860"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        initialize_app_data()

    @app.get("/health")
    def health() -> dict[str, Any]:
        status = config_status()
        return {"ok": True, "service": "knowledge-integrator", "config": status}

    @app.get("/api/config/status")
    def api_config_status() -> dict[str, Any]:
        return config_status()

    @app.post("/api/upload")
    async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
        return await handle_upload(file)

    @app.get("/api/textbooks")
    def api_textbooks() -> list[dict[str, Any]]:
        return list_textbooks()

    @app.get("/api/textbooks/{textbook_id}")
    def api_textbook(textbook_id: str) -> dict[str, Any]:
        return get_textbook(textbook_id)

    @app.delete("/api/textbooks/{textbook_id}")
    def api_delete_textbook(textbook_id: str) -> dict[str, Any]:
        return delete_textbook(textbook_id)

    @app.post("/api/knowledge/extract/{textbook_id}")
    async def api_extract(textbook_id: str, use_llm: bool = Query(True)) -> dict[str, Any]:
        return await extract_knowledge(textbook_id, use_llm=use_llm)

    @app.get("/api/knowledge/status/{textbook_id}")
    def api_knowledge_status(textbook_id: str) -> dict[str, Any]:
        graph = get_graph(textbook_id)
        return {"status": "ready", **graph["stats"]}

    @app.get("/api/knowledge/graph/merged")
    def api_merged_graph(limit: int = Query(900, ge=1, le=2000)) -> dict[str, Any]:
        return get_merged_graph(limit=limit)

    @app.get("/api/knowledge/graph/{textbook_id}")
    def api_graph(textbook_id: str, limit: int = Query(900, ge=1, le=2000)) -> dict[str, Any]:
        return get_graph(textbook_id, limit=limit)

    @app.post("/api/integrate/start")
    def api_integrate_start() -> dict[str, Any]:
        graph = ensure_merged_graph()
        return {"status": "ready", "graph": graph, "stats": integration_stats()}

    @app.get("/api/integrate/status")
    def api_integrate_status() -> dict[str, Any]:
        return {"status": "ready", "stats": integration_stats()}

    @app.get("/api/integrate/decisions")
    def api_decisions() -> list[dict[str, Any]]:
        return list_decisions()

    @app.put("/api/integrate/decisions/{decision_id}")
    def api_update_decision(decision_id: str, payload: DecisionUpdate) -> dict[str, Any]:
        return update_decision(decision_id, payload.model_dump(exclude_none=True))

    @app.get("/api/integrate/stats")
    def api_integration_stats() -> dict[str, Any]:
        return integration_stats()

    @app.post("/api/rag/index")
    def api_rag_index(
        sync_dify: bool = Query(True),
        sync_all: bool = Query(True),
        limit: int | None = Query(None, ge=1, le=10000),
        batch_size: int = Query(5000, ge=1, le=10000),
    ) -> dict[str, Any]:
        return build_rag_index(sync_dify=sync_dify, sync_all=sync_all, limit=limit, batch_size=batch_size)

    @app.get("/api/rag/status")
    def api_rag_status() -> dict[str, Any]:
        return rag_status()

    @app.post("/api/rag/sync/{textbook_id}")
    def api_rag_sync_textbook(textbook_id: str, batch_size: int = Query(5000, ge=1, le=10000)) -> dict[str, Any]:
        return sync_textbook_to_dify(textbook_id, batch_size=batch_size)

    @app.post("/api/rag/query")
    async def api_rag_query(payload: RagQuery) -> dict[str, Any]:
        return await rag_query(payload.question, payload.conversation_id)

    @app.post("/api/chat/message")
    async def api_chat_message(payload: ChatMessageIn) -> dict[str, Any]:
        return await chat_message(payload.session_id, payload.message)

    @app.get("/api/chat/history/{session_id}")
    def api_chat_history(session_id: str) -> list[dict[str, Any]]:
        return chat_history(session_id)

    @app.get("/api/multimodal/status")
    def api_multimodal_status() -> dict[str, Any]:
        return {
            "status": "cached",
            "items": [
                {"type": "mindmap", "title": "知识图谱结构视图", "status": "ready"},
                {"type": "flashcards", "title": "肺炎链球菌样例闪卡", "status": "ready"},
                {"type": "slides", "title": "整合报告可导出为讲义", "status": "placeholder"},
            ],
            "notebooklm": "optional_not_configured",
        }

    @app.post("/api/multimodal/generate")
    def api_multimodal_generate() -> dict[str, Any]:
        return {
            "status": "cached",
            "message": "NotebookLM 是可选输出层；当前返回缓存/降级学习材料。",
            "items": [
                {"type": "mindmap", "status": "ready"},
                {"type": "quiz", "status": "ready"},
                {"type": "slides", "status": "placeholder"},
            ],
        }

    @app.get("/api/multimodal/cached")
    def api_multimodal_cached() -> list[dict[str, Any]]:
        return [
            {"type": "mindmap", "title": "医学知识结构图", "description": "由当前图谱视图降级生成。"},
            {"type": "quiz", "title": "肺炎链球菌闯关题", "description": "复用内置游戏样例。"},
        ]

    @app.get("/api/multimodal/download/{artifact_type}")
    def api_multimodal_download(artifact_type: str) -> PlainTextResponse:
        if artifact_type in {"slides", "report", "notes"}:
            return PlainTextResponse(generate_report(), media_type="text/markdown; charset=utf-8")
        if artifact_type in {"mindmap", "flashcards", "quiz"}:
            return PlainTextResponse(
                '{"status":"cached","message":"该材料由前端图谱/游戏样例降级展示。"}',
                media_type="application/json; charset=utf-8",
            )
        return PlainTextResponse("该类型暂无缓存文件。", status_code=404)

    @app.get("/api/game/skill-tree")
    def api_game_skill_tree() -> dict[str, Any]:
        return game_skill_tree()

    @app.get("/api/game/level/{level_id}")
    def api_game_level(level_id: str) -> dict[str, Any]:
        return game_level(level_id)

    @app.post("/api/game/submit/{level_id}")
    def api_game_submit(level_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        level = game_level(level_id)
        answers = payload.get("answers", {})
        correct = 0
        for question in level["questions"]:
            if str(answers.get(question["id"])) == str(question["correctAnswer"]):
                correct += 1
        total = len(level["questions"])
        ratio = correct / total if total else 0
        stars = 3 if ratio >= 1 else 2 if ratio >= 0.8 else 1 if ratio >= 0.6 else 0
        return {"level_id": level_id, "correct": correct, "total": total, "stars": stars, "xp": correct * 10}

    @app.get("/api/game/progress")
    def api_game_progress() -> dict[str, Any]:
        return game_skill_tree()["playerProgress"]

    @app.get("/api/report/generate")
    def api_report_generate() -> dict[str, str]:
        return {"markdown": generate_report()}

    @app.get("/api/report/download")
    def api_report_download() -> PlainTextResponse:
        return PlainTextResponse(generate_report(), media_type="text/markdown; charset=utf-8")

    dist = settings.root_dir / "frontend" / "dist"
    if dist.exists():
        assets = dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/")
        def spa_index() -> FileResponse:
            return FileResponse(dist / "index.html")

        @app.get("/{path:path}")
        def spa_fallback(path: str) -> FileResponse:
            candidate = dist / path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
