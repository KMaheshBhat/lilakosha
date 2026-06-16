import importlib.resources
import logging
from pathlib import Path

import requests
from jinja2 import BaseLoader, Environment
from tqdm import tqdm

from cdm.core import Annotation, Session
from cdm.refine import GenreAndThemesResponse

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

    logger.info(
        f"Inspecting {len(record_files)} records for Genre & Theme Classification..."
    )
    service_url = f"{config['services']['inspector']}/v1/chat/completions"

    for file_path in tqdm(record_files, desc="Classifying Canvas Genre & Themes"):
        try:
            # 1. Load the standalone canvas session
            with open(file_path, "r", encoding="utf-8") as f:
                session = Session.model_validate_json(f.read())

            # 2. Idempotency Sniff Test
            if session.meta.primary_genre is not None or (
                session.meta.themes and len(session.meta.themes) > 0
            ):
                continue

            # 3. Generate structured prompt inputs from templates
            user_prompt = user_tmpl.render(session=session)
            system_prompt = system_tmpl.render(session=session)

            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 2048,
                "response_format": {
                    "type": "json_object",
                    "schema": GenreAndThemesResponse.model_json_schema(),
                },
            }

            # 4. Dispatch to inspector engine endpoint
            resp = requests.post(service_url, json=payload, timeout=120)
            resp.raise_for_status()

            response_json = resp.json()
            message_data = response_json["choices"][0]["message"]
            raw_content = message_data["content"]
            reasoning = message_data.get("reasoning_content")

            extracted_data = GenreAndThemesResponse.model_validate_json(raw_content)

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

    logger.info("✅ Genre & theme refinement script pass finished.")
