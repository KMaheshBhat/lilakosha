import glob
import importlib.resources
import logging
import os

import requests
from jinja2 import BaseLoader, Environment
from tqdm import tqdm

from cdm.core import Annotation, CharacterEntity, Session
from cdm.refine import CharacterSynthesisResponse

logger = logging.getLogger(__name__)


def load_jinja_templates(templates: list[str]) -> dict[str, str]:
    """Loads raw templates from the package directory."""
    try:
        result = {}
        ref = importlib.resources.files("steps.refine-characters.templates")
        for template in templates:
            template_str = (ref / f"{template}.jinja2").read_text(encoding="utf-8")
            result[template] = template_str.strip()
        return result
    except Exception as e:
        logger.error(f"Failed to load external prompt templates: {e}")
        raise


def run(config: dict) -> None:
    """LilaKosha Refinement Pass: Character Synthesis with robust parsing."""
    templates_str = load_jinja_templates(["system", "user", "character-detail"])
    jinja_env = Environment(loader=BaseLoader())
    user_tmpl = jinja_env.from_string(templates_str["user"])
    system_tmpl = jinja_env.from_string(templates_str["system"])
    character_detail_tmpl = jinja_env.from_string(templates_str["character-detail"])
    processed_vol = config["volumes"]["processed"]
    cdm_dir = os.path.join(processed_vol, "cdm")
    ledger_files = sorted(glob.glob(os.path.join(cdm_dir, "*.jsonl")))
    if not ledger_files:
        logger.error(
            "No CDM ledgers found in processed/cdm/. Run 'ingest-pippa' first."
        )
        return
    latest_ledger = ledger_files[-1]
    logger.info(
        f"Synthesizing Character Profiles in: {os.path.basename(latest_ledger)}"
    )
    with open(latest_ledger, "r", encoding="utf-8") as f_in:
        lines = f_in.readlines()
    updated_sessions = []
    service_url = f"{config['services']['summarizer']}/v1/chat/completions"
    for i, line in enumerate(tqdm(lines, desc="Structured Character Synthesis")):
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
                "schema": CharacterSynthesisResponse.model_json_schema(),
            },
        }
        try:
            resp = requests.post(service_url, json=payload, timeout=120)
            resp.raise_for_status()
            response_json = resp.json()
            message_data = response_json["choices"][0]["message"]
            raw_content = message_data["content"]
            reasoning = message_data.get("reasoning_content")
            extracted_data = CharacterSynthesisResponse.model_validate_json(raw_content)
            session.meta.user_pc_name = extracted_data.user_character.name
            user_character_content = character_detail_tmpl.render(
                extracted_data.user_character
            )
            bot_character_content = character_detail_tmpl.render(
                extracted_data.bot_character
            )
            bot_character_detail = CharacterEntity(
                kind="character",
                subkind="detail",
                entity_id=session.meta.bot_id or "unknown_bot",
                content=bot_character_content,
            )
            user_character_info = CharacterEntity(
                kind="character",
                subkind="info",
                entity_id="user",
                content=user_character_content,
            )
            print(
                f" > [{i + 1}] "
                f"Extracted:\n"
                f"  - Bot: {session.meta.bot_name}\n"
                f"  - UserPC: {extracted_data.user_character.name}\n"
            )
            session.children.insert(1, bot_character_detail)
            session.children.insert(2, user_character_info)
            annoations = [
                Annotation(
                    kind="refine-characters",
                    content="refined bot character details and user character info",
                    reasoning=reasoning,
                )
            ]
            if not session.meta.annotations:
                session.meta.annotations = []
            session.meta.annotations.extend(annoations)
            updated_sessions.append(session)
        except Exception as e:
            logger.error(f"Failed extraction pass for {session.meta.bot_name}: {e}")
            updated_sessions.append(session)
    # Physical Write to the Unified Ledger
    with open(latest_ledger, "w", encoding="utf-8") as f_out:
        for enriched_session in updated_sessions:
            # Output directly to uniform single-line JSONL strings
            f_out.write(enriched_session.model_dump_json() + "\n")
    logger.info("✅ Character refinement complete.")
