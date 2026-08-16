from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]

load_dotenv(BASE_DIR / ".env")
load_dotenv()


@dataclass(frozen=True)
class Settings:
	base_dir: Path = BASE_DIR
	data_dir: Path = BASE_DIR / "data"
	uploaded_documents_dir: Path = BASE_DIR / "data" / "uploaded_documents"
	pipeline_artifacts_dir: Path = BASE_DIR / "data" / "pipeline_artifacts"
	logs_dir: Path = BASE_DIR / "logs"
	case_memory_dir: Path = BASE_DIR / "data" / "case_memory"
	output_dir: Path = BASE_DIR / "output"
	prompts_dir: Path = BASE_DIR / "app" / "prompts"
	max_cases: int = int(os.getenv("MAX_CASES", "50"))
	chunk_size: int = int(os.getenv("CHUNK_SIZE", "5000"))
	retry_limit: int = int(os.getenv("RETRY_LIMIT", "3"))
	temperature: float = float(os.getenv("TEMPERATURE", "0.2"))
	model: str = os.getenv("MODEL", "openai/gpt-oss-120b")
	llm_provider: str = os.getenv("LLM_PROVIDER", "local")
	llm_api_key: str = os.getenv("LLM_API_KEY", "")
	llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1",)
	batch_size: int = int(os.getenv("BATCH_SIZE", "2"))
	max_prompt_tokens: int = int(os.getenv("MAX_PROMPT_TOKENS", "6500"))
	max_evidence_items: int = int(os.getenv("MAX_EVIDENCE_ITEMS", "20"))
	max_previous_case_summaries: int = int(os.getenv("MAX_PREVIOUS_CASE_SUMMARIES", "15"))
	max_completion_tokens: int = int(os.getenv("MAX_COMPLETION_TOKENS", "4000"))
	max_previous_cases_in_prompt: int = int(os.getenv("MAX_PREVIOUS_CASES_IN_PROMPT", "10"))
	# Rate limit configuration
	max_retries: int = int(os.getenv("MAX_RETRIES", "5"))
	retry_base_delay: float = float(os.getenv("RETRY_BASE_DELAY", "1.0"))
	retry_buffer: float = float(os.getenv("RETRY_BUFFER", "2.0"))
	request_throttle_delay: float = float(os.getenv("REQUEST_THROTTLE_DELAY", "0.5"))
	batch_delay: float = float(os.getenv("BATCH_DELAY", "5.0"))


settings = Settings()

DATA_DIR = settings.data_dir
UPLOADED_DOCUMENTS_DIR = settings.uploaded_documents_dir
PIPELINE_ARTIFACTS_DIR = settings.pipeline_artifacts_dir
LOGS_DIR = settings.logs_dir
CASE_MEMORY_DIR = settings.case_memory_dir
OUTPUT_DIR = settings.output_dir
PROMPTS_DIR = settings.prompts_dir
MODEL = settings.model
LLM_API_KEY = settings.llm_api_key
MAX_CASES = settings.max_cases
CHUNK_SIZE = settings.chunk_size
RETRY_LIMIT = settings.retry_limit
TEMPERATURE = settings.temperature
LLM_PROVIDER = settings.llm_provider
LLM_BASE_URL = settings.llm_base_url
BATCH_SIZE = settings.batch_size
MAX_PROMPT_TOKENS = settings.max_prompt_tokens
MAX_EVIDENCE_ITEMS = settings.max_evidence_items
MAX_PREVIOUS_CASE_SUMMARIES = settings.max_previous_case_summaries
MAX_COMPLETION_TOKENS = settings.max_completion_tokens
MAX_PREVIOUS_CASES_IN_PROMPT = settings.max_previous_cases_in_prompt


def ensure_directories() -> None:
	for directory in (
		DATA_DIR,
		UPLOADED_DOCUMENTS_DIR,
		PIPELINE_ARTIFACTS_DIR,
		LOGS_DIR,
		CASE_MEMORY_DIR,
		OUTPUT_DIR,
		PROMPTS_DIR,
	):
		directory.mkdir(parents=True, exist_ok=True)