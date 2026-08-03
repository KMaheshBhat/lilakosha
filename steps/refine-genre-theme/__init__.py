import importlib.resources
import logging
import time
from pathlib import Path

from jinja2 import BaseLoader, Environment
from tqdm import tqdm

from cdm.core import CategorizationItem, Document
from cdm.meta import add_annotation, update_meta
from cdm.refine import GenreAndThemesResponse
from inference import Message, OpenAIInference

logger = logging.getLogger(__name__)


class InferenceBudgetExhausted(Exception):
    """Internal exception to cleanly unwind execution loops."""

    pass


def load_jinja_templates(templates: list[str]) -> dict[str, str]:
    """Loads raw templates from the package directory."""
    try:
        result = {}
        ref = importlib.resources.files("steps.refine-genre-theme.templates")
        for template in templates:
            template_str = (ref / f"{template}.jinja2").read_text(
                encoding="utf-8"
            )
            result[template] = template_str.strip()
        return result
    except Exception as e:
        logger.error(f"Failed to load external prompt templates: {e}")
        raise


def run(config: dict) -> None:
    """
    LilaKosha Refinement Pass: Genre & Theme Classification.
    Processes standalone canvas documents within the records folder using an
    in-line metadata sniff test for robust idempotency, injecting item targets.
    """
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
        logger.warning(
            f"No canvas records found to classify inside {records_dir}"
        )
        return

    # Extract and Validate Target Range Markers
    params = config.get("parameters", {})
    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")

    if start_uuid or stop_uuid:
        logger.info(
            f"🎯 Targeted Refinement Scope Activated (Genre/Theme):\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )
    else:
        logger.info(
            "🔬 Refinement Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(
        f"Inspecting {len(record_files)} records for Genre & Theme Classification..."
    )

    skipped_range_count = 0
    binding = config["bindings"]["refine-genre-theme"]
    service = config["services"][binding["service"]]
    temperature = binding.get("temperature", 0.1)
    max_tokens = binding.get("max_tokens", 2048)
    inference = OpenAIInference.from_service(service)
    requests_per_minute = service.get("requests_per_minute")
    allows_think_control = service.get("allows_think_control", True)
    allows_extra_body = service.get("allows_extra_body", True)
    next_request_time: float | None = None
    max_inference_budget = binding.get("max_inference_budget")
    inference_counter = 0

    try:
        for file_path in tqdm(
            record_files, desc="Classifying Canvas Genre & Themes"
        ):
            record_uuid = file_path.stem

            # Check floor constraint boundary
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

                # 2. Idempotency Check aligned with structural CDM category definitions
                existing_categories = {
                    item.category
                    for item in document.items
                    if item.kind == "categorization"
                }
                if {"theme", "genre"}.issubset(existing_categories):
                    continue

                # Budget Boundary Verification
                if (
                    max_inference_budget
                    and inference_counter >= max_inference_budget
                ):
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
                        response_model=GenreAndThemesResponse,
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

                # 5. Inject structured CategorizationItems into timeline matrix safely
                existing_cat_count = sum(
                    1
                    for item in document.items
                    if item.kind == "categorization"
                )

                if "genre" not in existing_categories:
                    existing_cat_count += 1
                    genre_item = CategorizationItem(
                        id=f"categorization-{existing_cat_count:06d}",
                        kind="categorization",
                        category="genre",
                        value=extracted_data.primary_genre,
                        reasoning=reasoning,
                    )
                    document.items.append(genre_item)

                if "theme" not in existing_categories:
                    existing_cat_count += 1
                    theme_item = CategorizationItem(
                        id=f"categorization-{existing_cat_count:06d}",
                        kind="categorization",
                        category="theme",
                        value=extracted_data.themes,
                        reasoning=reasoning,
                    )
                    document.items.append(theme_item)

                # 6. Append tracking annotation
                add_annotation(
                    document,
                    kind="refine-genre-theme",
                    content=(
                        "classified primary genre and thematic indicators "
                        "as structured layout items"
                    ),
                    reasoning=reasoning,
                )

                # 7. Re-materialize runtime document stats
                update_meta(document)

                # 8. Commit changes back to disk with pretty-print layout
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(
                        document.model_dump_json(indent=2, by_alias=True)
                    )

            except InferenceBudgetExhausted:
                raise
            except Exception as e:
                logger.error(
                    f"Failed genre classification pass for canvas "
                    f"document {file_path.name}: {e}"
                )

    except InferenceBudgetExhausted:
        logger.info(
            f"🛑 Inference quota budget fully consumed "
            f"({max_inference_budget}/{max_inference_budget} requests allocation). "
            f"Gracefully terminating execution loops."
        )

    logger.info(
        f"✅ Genre & theme refinement script pass finished. "
        f"Skipped out-of-range: {skipped_range_count} records. "
        f"Total calls executed: {inference_counter}."
    )
