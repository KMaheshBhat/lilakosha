import importlib.resources
import logging
from pathlib import Path

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
    """
    LilaKosha Refinement Pass: Character Synthesis.
    Operates incrementally over discrete canvas record files using an in-line
    idempotency sniff test.
    """
    templates_str = load_jinja_templates(["system", "user", "character-detail"])
    jinja_env = Environment(loader=BaseLoader())
    user_tmpl = jinja_env.from_string(templates_str["user"])
    system_tmpl = jinja_env.from_string(templates_str["system"])
    character_detail_tmpl = jinja_env.from_string(templates_str["character-detail"])

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
        logger.warning(f"No canvas records found to refine inside {records_dir}")
        return

    logger.info(f"Inspecting {len(record_files)} records for Character Synthesis...")
    service_url = f"{config['services']['summarizer']}/v1/chat/completions"

    for file_path in tqdm(record_files, desc="Refining Canvas Character Profiles"):
        try:
            # 1. Load the standalone canvas session
            with open(file_path, "r", encoding="utf-8") as f:
                session = Session.model_validate_json(f.read())

            # 2. Idempotency Sniff Test
            # Look for an existing User Info entity to see if this script already ran
            already_refined = any(
                child.kind == "character"
                and child.subkind == "info"
                and child.entity_id == "user"
                for child in session.children
            )
            if already_refined:
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
                    "schema": CharacterSynthesisResponse.model_json_schema(),
                },
            }

            # 4. Dispatch to local abliterated inference engine
            resp = requests.post(service_url, json=payload, timeout=120)
            resp.raise_for_status()

            response_json = resp.json()
            message_data = response_json["choices"][0]["message"]
            raw_content = message_data["content"]
            reasoning = message_data.get("reasoning_content")

            extracted_data = CharacterSynthesisResponse.model_validate_json(raw_content)

            # 5. Hydrate session metadata and entities
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

            # Insert profiles cleanly right behind the original raw source layout
            session.children.insert(1, bot_character_detail)
            session.children.insert(2, user_character_info)

            # 6. Append tracking annotations
            refine_annotation = Annotation(
                kind="refine-characters",
                content="refined bot character details and user character info",
                reasoning=reasoning,
            )
            if not session.meta.annotations:
                session.meta.annotations = []
            session.meta.annotations.append(refine_annotation)

            # 7. Commit changes back to disk with pretty printing
            #    for engineering visibility
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(session.model_dump_json(indent=2))

        except Exception as e:
            logger.error(
                f"Failed character extraction pass for canvas "
                f"document {file_path.name}: {e}"
            )

    logger.info("✅ Character refinement script pass finished.")
