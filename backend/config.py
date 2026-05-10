from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


ROOT_DIR = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(ROOT_DIR / ".env")


class Settings:
    root_dir: Path = ROOT_DIR
    data_dir: Path = ROOT_DIR / "data"
    raw_textbook_dir: Path = ROOT_DIR / "教材"
    split_dir: Path = ROOT_DIR / "拆分结果"
    uploaded_dir: Path = data_dir / "textbooks"
    markdown_dir: Path = data_dir / "markdown"
    runtime_split_dir: Path = data_dir / "split"
    graph_dir: Path = data_dir / "graphs"
    output_dir: Path = data_dir / "outputs"
    database_path: Path = data_dir / "app.db"

    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "7860"))
    app_base_path: str = os.getenv("APP_BASE_PATH", "").strip().rstrip("/")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com").strip()
    model_name: str = os.getenv("MODEL_NAME", os.getenv("OPENAI_MODEL", "deepseek-v4-flash")).strip()

    dify_base_url: str = os.getenv("DIFY_BASE_URL", "").rstrip("/")
    dify_api_key: str = os.getenv("DIFY_API_KEY", "").strip()
    dify_knowledge_api_key: str = os.getenv("DIFY_KNOWLEDGE_API_KEY", "").strip()
    dify_dataset_id: str = os.getenv("DIFY_DATASET_ID", "").strip()
    markitdown_bin: str = os.getenv("MARKITDOWN_BIN", "").strip()

    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    ]

    @property
    def deepseek_ready(self) -> bool:
        return bool(self.openai_api_key and self.openai_base_url and self.model_name)

    @property
    def dify_chat_ready(self) -> bool:
        return bool(self.dify_base_url and self.dify_api_key)

    @property
    def dify_knowledge_ready(self) -> bool:
        return bool(self.dify_base_url and self.dify_knowledge_api_key and self.dify_dataset_id)

    def ensure_dirs(self) -> None:
        for path in [
            self.data_dir,
            self.uploaded_dir,
            self.markdown_dir,
            self.runtime_split_dir,
            self.graph_dir,
            self.output_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
