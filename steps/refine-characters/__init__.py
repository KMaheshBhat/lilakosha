import importlib.resources
import logging
from pathlib import Path

from jinja2 import BaseLoader, Environment
from tqdm import tqdm

from cdm.core import Annotation, CharacterItem, Session
from cdm.refine import CharacterSynthesisResponse
from inference import Message, OpenAIInference

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
    idempotency check, resolving pronouns and updating the sealed identity registry.
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

    # Extract and Validate Target Range Markers
    params = config.get("parameters", {})
    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")

    if start_uuid or stop_uuid:
        logger.info(
            f"🎯 Targeted Refinement Scope Activated (Characters):\n"
            f"   - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"   - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )
    else:
        logger.info(
            "🔬 Refinement Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(f"Inspecting {len(record_files)} records for Character Synthesis...")

    skipped_range_count = 0

    for file_path in tqdm(record_files, desc="Refining Canvas Character Profiles"):
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

            # 2. Idempotency Check
            #    Check for an existing character detail item for the bot or
            #    a refined user registry name
            already_refined = any(
                item.kind == "character" and item.subkind == "detail"
                for item in session.items
            )
            if already_refined:
                continue

            # # 3. Generate structured prompt inputs from templates
            # user_prompt = user_tmpl.render(session=session)
            # system_prompt = system_tmpl.render(session=session)

            # payload = {
            #     "messages": [
            #         {"role": "system", "content": system_prompt},
            #         {"role": "user", "content": user_prompt},
            #     ],
            #     "temperature": 0.1,
            #     "max_tokens": 4096,
            #     "response_format": {
            #         "type": "json_object",
            #         "schema": CharacterSynthesisResponse.model_json_schema(),
            #     },
            # }

            # # 4. Dispatch to local abliterated inference engine
            # resp = requests.post(service_url, json=payload, timeout=120)
            # resp.raise_for_status()

            # response_json = resp.json()
            # message_data = response_json["choices"][0]["message"]
            # raw_content = message_data["content"]
            # reasoning = message_data.get("reasoning_content")

            # extracted_data = CharacterSynthesisResponse.model_validate_json(raw_content)
            # logger.debug(f"extracted_data: {extracted_data}")

            # 3. Generate structured prompt inputs from templates
            user_prompt = user_tmpl.render(session=session)
            system_prompt = system_tmpl.render(session=session)
            binding = config["bindings"]["refine-characters"]
            service = config["services"][binding["service"]]
            inference = OpenAIInference.from_service(service)
            result = inference.generate(
                messages=[
                    Message.system(system_prompt),
                    Message.user(user_prompt),
                ],
                response_model=CharacterSynthesisResponse,
                temperature=0.1,
                max_tokens=4096,
            )
            extracted_data = result.value
            reasoning = result.reasoning
            logger.debug(f"extracted_data: {extracted_data}")

            # 5. Update the Authoritative Identity Registry in SessionMeta
            bot_id = session.meta.bot_id or "unknown_bot"

            # Dynamically import cdm.core's PronounSet to avoid namespace collisions
            # with the refine model
            from cdm.core import PronounSet as CorePronounSet

            for identity in session.meta.identities:
                if identity.entity_id == "user":
                    # A. Force gender resolution to strict type-safe literals
                    user_gender_raw = extracted_data.user_character.gender.lower()
                    resolved_user_gender = (
                        "male"
                        if user_gender_raw == "male"
                        else "female"
                        if user_gender_raw == "female"
                        else "neutral"
                        if user_gender_raw == "neutral"
                        else "unknown"
                    )

                    identity.name = extracted_data.user_character.name
                    identity.gender = resolved_user_gender

                    # B. Re-hydrate using cdm.core's expected model type
                    identity.pronouns = CorePronounSet(
                        subjective=extracted_data.user_character.pronouns.subjective,
                        objective=extracted_data.user_character.pronouns.objective,
                        possessive=extracted_data.user_character.pronouns.possessive,
                    )

                elif identity.entity_id == bot_id:
                    # A. Force gender resolution to strict type-safe literals
                    bot_gender_raw = extracted_data.bot_character.gender.lower()
                    resolved_bot_gender = (
                        "male"
                        if bot_gender_raw == "male"
                        else "female"
                        if bot_gender_raw == "female"
                        else "neutral"
                        if bot_gender_raw == "neutral"
                        else "unknown"
                    )

                    identity.name = extracted_data.bot_character.name
                    identity.gender = resolved_bot_gender

                    # B. Re-hydrate using cdm.core's expected model type
                    identity.pronouns = CorePronounSet(
                        subjective=extracted_data.bot_character.pronouns.subjective,
                        objective=extracted_data.bot_character.pronouns.objective,
                        possessive=extracted_data.bot_character.pronouns.possessive,
                    )

            # 6. Render deep-lore narrative line items
            user_character_content = character_detail_tmpl.render(
                extracted_data.user_character
            )
            bot_character_content = character_detail_tmpl.render(
                extracted_data.bot_character
            )

            bot_character_detail = CharacterItem(
                kind="character",
                subkind="detail",
                entity_id=bot_id,
                content=bot_character_content,
            )
            user_character_info = CharacterItem(
                kind="character",
                subkind="info",
                entity_id="user",
                content=user_character_content,
            )

            # Prepend the newly generated character deep-lore snapshots to
            # the transactional timeline
            session.items.insert(0, bot_character_detail)
            session.items.insert(1, user_character_info)

            # 7. Append tracking annotations safely to satisfy static type checking
            if session.meta.annotations is None:
                session.meta.annotations = []

            session.meta.annotations.append(
                Annotation(
                    kind="refine-characters",
                    content=(
                        "refined bot character details and user character info "
                        "inside registry and timeline"
                    ),
                    reasoning=reasoning,
                )
            )

            # 8. Commit changes back to disk
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(session.model_dump_json(indent=2))

        except Exception as e:
            logger.error(
                f"Failed character extraction pass for canvas "
                f"document {file_path.name}: {e}"
            )

    logger.info(
        f"✅ Character refinement script pass finished. "
        f"Skipped out-of-range: {skipped_range_count} records."
    )
