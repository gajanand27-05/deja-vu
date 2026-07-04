"""Runtime settings resolved from env + sensible defaults.

Kept as a plain dataclass loaded once at CLI startup so downstream code doesn't
touch os.environ directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"


@dataclass(frozen=True)
class Settings:
    llm_api_key: str | None
    llm_provider: str
    llm_model: str
    embedding_model: str
    data_dir: Path
    learner_name: str

    @property
    def has_llm_key(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def snapshot_path(self) -> Path:
        return self.data_dir / "ui_snapshot.json"


def load_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env", override=False)
    data_dir = Path(os.getenv("DEJA_DATA_DIR", str(DEFAULT_DATA_DIR))).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        llm_api_key=os.getenv("LLM_API_KEY") or None,
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        data_dir=data_dir,
        learner_name=os.getenv("DEJA_LEARNER_NAME", "you"),
    )
