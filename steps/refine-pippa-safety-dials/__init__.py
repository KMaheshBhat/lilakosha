import importlib.resources
import logging
import time
from pathlib import Path

from jinja2 import BaseLoader, Environment
from tqdm import tqdm

from cdm.core import CategorizationItem, Document
from cdm.meta import add_annotation, remove_annotation, update_meta
from cdm.refine import SafetyDialsResponse
from inference import Message, OpenAIInference

logger = logging.getLogger(__name__)


class InferenceBudgetExhausted(Exception):
    """Internal exception to cleanly unwind execution loops."""

    pass


def load_jinja_templates(templates: list[str]) -> dict[str, str]:
    """Loads raw templates from the package directory."""
    try:
        result = {}
        ref = importlib.resources.files("steps.refine-pippa-safety-dials.templates")
        for template in templates:
            template_str = (ref / f"{template}.jinja2").read_text(encoding="utf-8")
            result[template] = template_str.strip()
        return result
    except Exception as e:
        logger.error(f"Failed to load external prompt templates: {e}")
        raise


def run(config: dict) -> None:
    """
    LilaKosha Refinement Pass: Safety Dials Classification (PIPPA) (v2).
    Iterates incrementally over individual CDM Document files using an explicit
    metadata sniff test for idempotency, appending structured categorization layouts.
    """
    # v2: Fail-fast validation of required config
    try:
        binding = config["bindings"]["refine-pippa-safety-dials"]
        service = config["services"][binding["service"]]
    except (KeyError, TypeError) as e:
        logger.error(
            f"Failed to resolve inference config for refine-pippa-safety-dials: {e}"
        )
        return

    templates_str = load_jinja_templates(["system", "user"])
    jinja_env = Environment(loader=BaseLoader())
    user_tmpl = jinja_env.from_string(templates_str["user"])
    system_tmpl = jinja_env.from_string(templates_str["system"])

    # Resolve paths from configuration volumes
    processed_vol = Path(config["volumes"]["processed"])
    records_dir = processed_vol / "cdm" / "records"

    if not records_dir.exists():
        logger.error(
            f"Records directory not found: {records_dir}. Run ingestion first."
        )
        return

    record_files = sorted(records_dir.glob("*.json"))
    if not record_files:
        logger.warning(f"No canvas records found to evaluate inside {records_dir}")
        return

    # Extract and Validate Target Range Markers
    params = config.get("parameters", {})
    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")

    # v2: Pre-filter record_files by file.stem before opening/parsing
    if start_uuid or stop_uuid:
        record_files = [
            f
            for f in record_files
            if (not start_uuid or f.stem >= str(start_uuid))
            and (not stop_uuid or f.stem <= str(stop_uuid))
        ]
        logger.info(
            f"🎯 Targeted Refinement Scope Activated (PIPPA Safety Dials v2):\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}\n"
            f"    - Pre-filtered to {len(record_files)} candidate files"
        )
    else:
        logger.info(
            "🔬 Refinement Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(
        f"Inspecting {len(record_files)} records for PIPPA "
        "Safety Dials Classification (v2)..."
    )

    skipped_range_count = 0
    temperature = binding.get("temperature", 0.1)
    max_tokens = binding.get("max_tokens", 2048)
    inference = OpenAIInference.from_service(service)
    requests_per_minute = service.get("requests_per_minute")
    allows_think_control = service.get("allows_think_control", True)
    allows_extra_body = service.get("allows_extra_body", True)
    next_request_time: float | None = None
    max_inference_budget = binding.get("max_inference_budget")
    inference_counter = 0

    processed_count = 0
    error_count = 0

    try:
        for file_path in tqdm(record_files, desc="Evaluating Canvas Safety Dials (v2)"):
            record_uuid = file_path.stem

            # Check floor constraint boundary
            # (should not happen after pre-filter, but keep for safety)
            if start_uuid and record_uuid < str(start_uuid):
                skipped_range_count += 1
                continue

            # Check ceiling constraint boundary
            if stop_uuid and record_uuid > str(stop_uuid):
                skipped_range_count += 1
                continue

            try:
                # 1. Load the standalone canvas document
                with open(file_path, "r", encoding="utf-8") as f:
                    document = Document.model_validate_json(f.read())

                # v2: Source scoping - only process PIPPA records
                source = document.meta.source or {}
                if source.get("source_identity") != "PygmalionAI/PIPPA":
                    continue

                # 2. Idempotency Check aligned with structural CDM category definitions
                existing_categories = {
                    item.category
                    for item in document.items
                    if item.kind == "categorization"
                }
                if {"sexuality", "violence", "toxicity"}.issubset(existing_categories):
                    continue

                # Budget Boundary Verification
                if max_inference_budget and inference_counter >= max_inference_budget:
                    raise InferenceBudgetExhausted()

                # 3. Generate structured prompt inputs from templates
                user_prompt = user_tmpl.render(session=document)
                system_prompt = system_tmpl.render(session=document)

                if requests_per_minute and next_request_time is not None:
                    now = time.monotonic()
                    if now < next_request_time:
                        time.sleep(next_request_time - now)

                extra_body_payload = (
                    {"thinking_budget_tokens": 0} if allows_extra_body else {}
                )
                reasoning_effort = "none" if allows_think_control else None

                try:
                    result = inference.generate(
                        messages=[
                            Message.system(system_prompt),
                            Message.user(user_prompt),
                        ],
                        response_model=SafetyDialsResponse,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        reasoning_effort=reasoning_effort,
                        extra_body=extra_body_payload,
                    )
                finally:
                    inference_counter += 1
                    if requests_per_minute:
                        interval = 60.0 / requests_per_minute
                        next_request_time = time.monotonic() + interval

                extracted_data = result.value
                reasoning = result.reasoning
                logger.debug(f"extracted_data: {extracted_data}")

                # 5. Inject structured CategorizationItems into timeline layout
                existing_cat_count = sum(
                    1 for item in document.items if item.kind == "categorization"
                )

                safety_mappings = [
                    ("sexuality", extracted_data.sexual_axis),
                    ("violence", extracted_data.violence_axis),
                    ("toxicity", extracted_data.toxicity_axis),
                ]

                for category_name, axis_value in safety_mappings:
                    if category_name not in existing_categories:
                        existing_cat_count += 1
                        item_id = f"categorization-{existing_cat_count:06d}"

                        safety_item = CategorizationItem(
                            id=item_id,
                            kind="categorization",
                            category=category_name,
                            value=axis_value,
                            reasoning=reasoning,
                        )
                        document.items.append(safety_item)

                # 6. Append tracking annotation
                # v2: Clean annotation hygiene
                remove_annotation(document, "refine-pippa-safety-dials")
                add_annotation(
                    document,
                    kind="refine-pippa-safety-dials",
                    content=(
                        "classified safety axes for the document and "
                        "appended discrete serialization categorization items"
                    ),
                    reasoning=reasoning,
                )

                # 7. Materialize runtime stats to account for layout mutation
                update_meta(document)

                # 8. Commit changes back to disk with pretty-print layout
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(document.model_dump_json(indent=2, by_alias=True))

                processed_count += 1

            except InferenceBudgetExhausted:
                raise
            except Exception as e:
                logger.error(
                    f"Failed safety evaluation pass for canvas "
                    f"document {file_path.name}: {e}"
                )
                error_count += 1

    except InferenceBudgetExhausted:
        logger.info(
            f"🛑 Inference quota budget fully consumed "
            f"({max_inference_budget}/{max_inference_budget} requests allocation). "
            f"Gracefully terminating execution loops."
        )

    logger.info(
        f"✅ Safety dials refinement script pass (v2) finished. "
        f"Processed: {processed_count}, "
        f"Skipped (range): {skipped_range_count}, "
        f"Errors: {error_count}, "
        f"Total calls executed: {inference_counter}."
    )
