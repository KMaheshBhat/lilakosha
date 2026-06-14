import glob
import importlib.resources
import logging
import os

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
    """LilaKosha Refinement Pass: Safety Dials Classification with robust parsing."""
    templates_str = load_jinja_templates(["system", "user"])
    jinja_env = Environment(loader=BaseLoader())
    user_tmpl = jinja_env.from_string(templates_str["user"])
    system_tmpl = jinja_env.from_string(templates_str["system"])
    processed_vol = config["volumes"]["processed"]
    cdm_dir = os.path.join(processed_vol, "cdm")
    ledger_files = sorted(glob.glob(os.path.join(cdm_dir, "*.jsonl")))
    if not ledger_files:
        logger.error(
            "No CDM ledgers found in processed/cdm/. Run 'ingest-pippa' first."
        )
        return
    latest_ledger = ledger_files[-1]
    logger.info(f"Classifying Safety Dials in: {os.path.basename(latest_ledger)}")
    with open(latest_ledger, "r", encoding="utf-8") as f_in:
        lines = f_in.readlines()
    updated_sessions = []
    service_url = f"{config['services']['inspector']}/v1/chat/completions"
    for i, line in enumerate(tqdm(lines, desc="Safety Dials Classification")):
        session = Session.model_validate_json(line)
        user_prompt = user_tmpl.render(session=session)
        system_prompt = system_tmpl.render(session=session)
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
            "response_format": {
                "type": "json_object",
                "schema": SafetyDialsResponse.model_json_schema(),
            },
        }
        try:
            resp = requests.post(service_url, json=payload, timeout=120)
            resp.raise_for_status()
            response_json = resp.json()
            message_data = response_json["choices"][0]["message"]
            raw_content = message_data["content"]
            reasoning = message_data.get("reasoning_content")
            extracted_data = SafetyDialsResponse.model_validate_json(raw_content)
            session.meta.sexual_axis = extracted_data.sexual_axis
            session.meta.violence_axis = extracted_data.violence_axis
            session.meta.toxicity_axis = extracted_data.toxicity_axis
            print(
                f" > [{i + 1}] "
                f"Classified:\n"
                f"  - Sexual: {extracted_data.sexual_axis.value}\n"
                f"  - Violence: {extracted_data.violence_axis.value}\n"
                f"  - Toxicity: {extracted_data.toxicity_axis.value}\n"
            )
            annotations = [
                Annotation(
                    kind="refine-safety-dials",
                    content="classified safety axes for the session",
                    reasoning=reasoning,
                )
            ]
            if not session.meta.annotations:
                session.meta.annotations = []
            session.meta.annotations.extend(annotations)
            updated_sessions.append(session)
        except Exception as e:
            logger.error(f"Failed classification pass for {session.meta.bot_name}: {e}")
            updated_sessions.append(session)
    # Physical Write to the Unified Ledger
    with open(latest_ledger, "w", encoding="utf-8") as f_out:
        for enriched_session in updated_sessions:
            f_out.write(enriched_session.model_dump_json() + "\n")
    logger.info("✅ Safety dials refinement complete.")
