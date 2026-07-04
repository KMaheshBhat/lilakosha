import importlib.resources
import logging
import time
from pathlib import Path

from jinja2 import BaseLoader, Environment
from tqdm import tqdm

from cdm.core import Annotation, Session
from cdm.refine import GenreAndThemesResponse
from inference import Message, OpenAIInference

logger = logging.getLogger(__name__)


def load_jinja_templates(templates: list[str]) -> dict[str, str]:
    """Loads raw templates from the package directory."""
    try:
        result = {}
        ref = importlib.resources.files("steps.refine-genre-theme.templates")
        for template in templates:
            template_str = (ref / f"{template}.jinja2").read_text(encoding="utf-8")
            result[template] = template_str.strip()
        return result
    except Exception as e:
        logger.error(f"Failed to load external prompt templates: {e}")
        raise


def run(config: dict) -> None:
    """
    LilaKosha Refinement Pass: Genre & Theme Classification.
    Processes standalone canvas documents within the records folder using an
    in-line metadata sniff test for robust idempotency.
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
        logger.warning(f"No canvas records found to classify inside {records_dir}")
        return

    # Extract and Validate Target Range Markers
    params = config.get("parameters", {})
    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")

    if start_uuid or stop_uuid:
        logger.info(
            f"🎯 Targeted Refinement Scope Activated (Genre/Theme):\n"
            f"   - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"   - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
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
    requests_per_minute = service["requests_per_minute"]
    next_request_time: float | None = None

    for file_path in tqdm(record_files, desc="Classifying Canvas Genre & Themes"):
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
            # 1. Load the standalone canvas session
            with open(file_path, "r", encoding="utf-8") as f:
                session = Session.model_validate_json(f.read())

            # --- Health Guard Gate ---
            # Skip if a previous telemetry pass explicitly identified
            # this file as defective
            if session.meta and session.meta.healthy is False:
                continue

            # 2. Idempotency Sniff Test
            if session.meta.primary_genre is not None or (
                session.meta.themes and len(session.meta.themes) > 0
            ):
                continue

            # 3. Generate structured prompt inputs from templates
            user_prompt = user_tmpl.render(session=session)
            system_prompt = system_tmpl.render(session=session)
            if requests_per_minute and next_request_time is not None:
                now = time.monotonic()
                if now < next_request_time:
                    time.sleep(next_request_time - now)
            result = inference.generate(
                messages=[
                    Message.system(system_prompt),
                    Message.user(user_prompt),
                ],
                response_model=GenreAndThemesResponse,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if requests_per_minute:
                next_request_time = time.monotonic() + (60.0 / requests_per_minute)
            extracted_data = result.value
            reasoning = result.reasoning
            logger.debug(f"extracted_data: {extracted_data}")

            # 5. Hydrate session metadata genre and theme configurations
            session.meta.primary_genre = extracted_data.primary_genre
            session.meta.themes = extracted_data.themes

            # 6. Append tracking annotations cleanly
            if session.meta.annotations is None:
                session.meta.annotations = []

            session.meta.annotations.append(
                Annotation(
                    kind="refine-genre-theme",
                    content="classified genre and themes for the session",
                    reasoning=reasoning,
                )
            )

            # 7. Commit changes back to disk with pretty-print layout
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(session.model_dump_json(indent=2))

        except Exception as e:
            logger.error(
                f"Failed genre classification pass for canvas "
                f"document {file_path.name}: {e}"
            )

    logger.info(
        f"✅ Genre & theme refinement script pass finished. "
        f"Skipped out-of-range: {skipped_range_count} records."
    )
