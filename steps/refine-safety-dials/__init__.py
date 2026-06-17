import importlib.resources
import logging
from pathlib import Path

import requests
from jinja2 import BaseLoader, Environment
from tqdm import tqdm

from cdm.core import Annotation, Session
from cdm.refine import SafetyDialsResponse

logger = logging.getLogger(__name__)


def load_jinja_templates(templates: list[str]) -> dict[str, str]:
    """Loads raw templates from the package directory."""
    try:
        result = {}
        ref = importlib.resources.files("steps.refine-safety-dials.templates")
        for template in templates:
            template_str = (ref / f"{template}.jinja2").read_text(encoding="utf-8")
            result[template] = template_str.strip()
        return result
    except Exception as e:
        logger.error(f"Failed to load external prompt templates: {e}")
        raise


def run(config: dict) -> None:
    """
    LilaKosha Refinement Pass: Safety Dials Classification.
    Iterates incrementally over individual canvas files using an explicit metadata
    sniff test for idempotency.
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
        logger.warning(f"No canvas records found to evaluate inside {records_dir}")
        return

    logger.info(
        f"Inspecting {len(record_files)} records for Safety Dials Classification..."
    )
    service_url = f"{config['services']['inspector']}/v1/chat/completions"

    for file_path in tqdm(record_files, desc="Evaluating Canvas Safety Dials"):
        try:
            # 1. Load the standalone canvas session
            with open(file_path, "r", encoding="utf-8") as f:
                session = Session.model_validate_json(f.read())

            # --- Health Guard Gate ---
            # Skip if a previous telemetry pass explicitly identified
            # this file as defective
            if session.meta and session.meta.healthy is False:
                continue

            # 2. Idempotency Check
            if (
                session.meta.sexual_axis is not None
                or session.meta.violence_axis is not None
                or session.meta.toxicity_axis is not None
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
                    "schema": SafetyDialsResponse.model_json_schema(),
                },
            }

            # 4. Dispatch to inspector engine endpoint
            resp = requests.post(service_url, json=payload, timeout=120)
            resp.raise_for_status()

            response_json = resp.json()
            message_data = response_json["choices"][0]["message"]
            raw_content = message_data["content"]
            reasoning = message_data.get("reasoning_content")

            extracted_data = SafetyDialsResponse.model_validate_json(raw_content)

            # 5. Hydrate session metadata safety properties
            #    Ensure proper type alignment depending on whether your schema uses
            #    string literals or explicit types
            session.meta.sexual_axis = extracted_data.sexual_axis
            session.meta.violence_axis = extracted_data.violence_axis
            session.meta.toxicity_axis = extracted_data.toxicity_axis

            # 6. Append tracking annotations safely to satisfy static type checking
            if session.meta.annotations is None:
                session.meta.annotations = []

            session.meta.annotations.append(
                Annotation(
                    kind="refine-safety-dials",
                    content="classified safety axes for the session",
                    reasoning=reasoning,
                )
            )

            # 7. Commit changes back to disk with pretty-print layout
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(session.model_dump_json(indent=2))

        except Exception as e:
            logger.error(
                f"Failed safety evaluation pass for canvas "
                f"document {file_path.name}: {e}"
            )

    logger.info("✅ Safety dials refinement script pass finished.")
