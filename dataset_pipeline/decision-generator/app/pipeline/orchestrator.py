from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from pathlib import Path

from langsmith import traceable
from app.agents.generation_agent import DecisionGenerationAgent
from app.agents.validation_agent import DecisionValidationAgent
from app.config import (
    BATCH_SIZE,
    MAX_CASES,
    OUTPUT_DIR,
    PROMPTS_DIR,
    RETRY_LIMIT,
    ensure_directories,
    settings,
)
from app.context.enterprise_context_builder import EnterpriseContextBuilder
from app.export.csv_export import export_csv
from app.intelligence.document_intelligence import DocumentIntelligence
from app.llm.local_client import LocalLLMClient
from app.llm.openai_client import OpenAIClient
from app.logging_utils import configure_logging
from app.models.decision_case import DecisionCase
from app.models.pipeline import GenerationRequest, GenerationResponse, PipelineArtifacts
from app.prompts.builder import PromptBuilder
from app.storage.local_store import LocalFileStore


logger = logging.getLogger(__name__)


def _current_quarter() -> str:
    now = datetime.utcnow()
    quarter = (now.month - 1) // 3 + 1
    return f"Q{quarter}-{now.year}"


def _infer_quarter_from_text(text: str) -> str | None:
    patterns = [
        r"Q([1-4])[-\s]?([12][0-9]{3})",
        r"quarter\s+ended\s+([A-Za-z]+\s+[0-9]{1,2},\s+[12][0-9]{3})",
        r"fiscal\s+quarter\s+([A-Za-z]+\s+[0-9]{1,2},\s+[12][0-9]{3})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if len(match.groups()) == 2:
                return f"Q{match.group(1)}-{match.group(2)}"
            return match.group(1)
    return None


class Pipeline:
    def __init__(self) -> None:
        ensure_directories()
        configure_logging()
        self.store = LocalFileStore()
        self.document_intelligence = DocumentIntelligence()
        self.context_builder = EnterpriseContextBuilder()
        self.prompt_builder = PromptBuilder(PROMPTS_DIR)
        openai_client = OpenAIClient()
        self.llm_client = openai_client if openai_client.is_configured() else LocalLLMClient()
        self.generation_agent = DecisionGenerationAgent(self.llm_client, self.prompt_builder)
        self.validation_agent = DecisionValidationAgent(self.llm_client, self.prompt_builder)

    def _collect_document_paths(self, uploaded_files: list[tuple[str, bytes]] | None) -> list[Path]:
        if uploaded_files:
            return self.store.save_uploaded_documents(uploaded_files)
        return self.store.list_uploaded_documents()

    def _load_previous_cases(self, quarter: str) -> list[DecisionCase]:
        cases: list[DecisionCase] = []
        for item in self.store.load_case_memory():
            try:
                case = DecisionCase.model_validate(item)
            except Exception:
                continue
            if case.quarter == quarter:
                cases.append(case)
        return cases

    def _run_batch(
        self,
        *,
        context,
        previous_cases: list[DecisionCase],
        accepted_cases: list[DecisionCase],
        batch_target: int,
        starting_case_id: int,
    ) -> tuple[list[DecisionCase], list[DecisionCase]]:
        """Generate + validate a single batch, with targeted repair retries.

        First attempt: full generation via the Generation Agent.
        Subsequent attempts: targeted repair of the previously-generated batch
        using only the fields flagged by the Validation Agent (no full regen).

        Returns (all_generated_cases_this_batch, accepted_cases_this_batch).
        """
        combined_history = previous_cases + accepted_cases
        candidate_cases: list[DecisionCase] = []
        accepted_this_batch: list[DecisionCase] = []

        # Attempt 1: initial generation
        logger.info(
            "batch_attempt=1 batch_target=%s accepted_so_far=%s starting_case_id=%s",
            batch_target,
            len(accepted_cases),
            starting_case_id,
        )
        candidate_cases = self.generation_agent.generate(
            context=context,
            previous_cases=combined_history,
            requested_cases=batch_target,
            feedback=None,
            starting_case_id=starting_case_id,
        )
        validation_result = self.validation_agent.validate(candidate_cases, combined_history)
        if validation_result.status == "PASS":
            return candidate_cases, validation_result.accepted_cases

        logger.info("batch_validation_failed feedback=%s", validation_result.feedback)

        # Attempts 2..RETRY_LIMIT: targeted repair of the flagged cases.
        for attempt in range(2, RETRY_LIMIT + 1):
            logger.info(
                "batch_attempt=%s (repair) flagged_cases=%s",
                attempt,
                list(validation_result.feedback_by_case.keys()),
            )
            candidate_cases = self.generation_agent.repair(
                context=context,
                previous_cases=combined_history,
                current_cases=candidate_cases,
                feedback_by_case=validation_result.feedback_by_case,
                general_feedback=validation_result.feedback,
            )
            # Preserve stable case_id numbering across the batch.
            for offset, case in enumerate(candidate_cases):
                case.case_id = starting_case_id + offset

            validation_result = self.validation_agent.validate(candidate_cases, combined_history)
            if validation_result.status == "PASS":
                accepted_this_batch = validation_result.accepted_cases
                break
            logger.info("batch_validation_failed feedback=%s", validation_result.feedback)

        return candidate_cases, accepted_this_batch

    # LangSmith's ``metadata`` parameter must be a mapping.  Passing a callback
    # makes recent LangSmith releases fail before ``run`` is entered.
    @traceable(name="Pipeline Run")
    def run(
        self,
        request: GenerationRequest,
        uploaded_files: list[tuple[str, bytes]] | None = None,
    ) -> GenerationResponse:
        requested_cases = min(max(request.max_cases, 1), MAX_CASES)
        document_paths = self._collect_document_paths(uploaded_files)
        if not document_paths:
            raise ValueError("at least one uploaded PDF is required before running the pipeline")

        run_id = self.store.latest_run_id()
        parsed_documents = self.document_intelligence.parse_documents(document_paths)
        quarter = (
            request.quarter
            or _infer_quarter_from_text(" ".join(" ".join(doc.pages) for doc in parsed_documents))
            or _current_quarter()
        )
        enterprise_context = self.context_builder.build(parsed_documents, quarter)
        previous_cases = self._load_previous_cases(quarter)

        artifacts = PipelineArtifacts(parsed_documents=parsed_documents, enterprise_context=enterprise_context)
        accepted_cases: list[DecisionCase] = []
        all_generated_cases: list[DecisionCase] = []

        # Iterative batching loop: keep requesting small batches until we hit requested_cases
        # or exhaust our attempt budget.
        max_batch_iterations = max(1, (requested_cases + BATCH_SIZE - 1) // BATCH_SIZE) + 2
        for batch_index in range(max_batch_iterations):
            if len(accepted_cases) >= requested_cases:
                break
            remaining = requested_cases - len(accepted_cases)
            batch_target = min(BATCH_SIZE, remaining)
            starting_case_id = len(accepted_cases) + 1

            logger.info(
                "batch_start index=%s target=%s remaining=%s accepted=%s",
                batch_index,
                batch_target,
                remaining,
                len(accepted_cases),
            )

            candidate_cases, accepted_this_batch = self._run_batch(
                context=enterprise_context,
                previous_cases=previous_cases,
                accepted_cases=accepted_cases,
                batch_target=batch_target,
                starting_case_id=starting_case_id,
            )

            all_generated_cases.extend(candidate_cases)
            if not accepted_this_batch:
                logger.warning("batch_index=%s produced no accepted cases; stopping loop", batch_index)
                break
            accepted_cases.extend(accepted_this_batch)
            
            # Add inter-batch delay to stay within TPM budget
            if batch_index < max_batch_iterations - 1 and len(accepted_cases) < requested_cases:
                logger.info(f"Waiting {settings.batch_delay}s before next batch...")
                time.sleep(settings.batch_delay)

        if not accepted_cases:
            raise RuntimeError("validation failed to accept any cases across all batches")

        # Trim in case we overshot (unlikely because batch_target caps at remaining).
        accepted_cases = accepted_cases[:requested_cases]
        # Ensure case_ids are contiguous and unique.
        for idx, case in enumerate(accepted_cases, start=1):
            case.case_id = idx

        artifacts.generated_cases = all_generated_cases
        artifacts.validated_cases = accepted_cases

        self.store.append_case_memory([case.model_dump() for case in accepted_cases])
        run_dir = self.store.run_dir(run_id)
        self.store.save_json(
            run_dir,
            "parsed_documents.json",
            [document.model_dump(mode="json") for document in parsed_documents],
        )
        self.store.save_json(run_dir, "enterprise_context.json", enterprise_context.model_dump())
        self.store.save_json(
            run_dir,
            "generated_cases.json",
            [case.model_dump() for case in artifacts.generated_cases],
        )
        self.store.save_json(
            run_dir,
            "validated_cases.json",
            [case.model_dump() for case in accepted_cases],
        )

        output_path = OUTPUT_DIR / "generated.csv"
        export_csv([case.model_dump() for case in accepted_cases], output_path)

        artifact_names = [
            "parsed_documents.json",
            "enterprise_context.json",
            "generated_cases.json",
            "validated_cases.json",
            "generated.csv",
        ]
        return GenerationResponse(
            run_id=run_id,
            quarter=quarter,
            requested_cases=requested_cases,
            accepted_cases=len(accepted_cases),
            output_file=output_path.name,
            pipeline_artifacts=artifact_names,
        )
