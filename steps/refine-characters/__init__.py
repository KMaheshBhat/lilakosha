import glob
import importlib.resources
import json
import logging
import os
import re

import requests
from tqdm import tqdm

from cdm.models import Session, TurnEntity

logger = logging.getLogger(__name__)


def get_chat_history_dict(session: dict) -> str:
    """Labels turns to help the model triangulate User PC identity."""
    bot_name = session["meta"].get("bot_name", "the character")
    turns = [c for c in session["children"] if c["kind"] == "turn"]
    history = ""
    # Use the top 50 turns to establish names and personalities
    for turn in turns[:50]:
        role = "USER" if turn["actor_id"] == "user" else bot_name
        history += f"{role}: {turn['prose']}\n"
    return history


def get_chat_history(session: Session) -> str:
    """Labels turns to help the model triangulate User PC identity."""
    # 1. Access attributes directly via dot notation.
    #    Since bot_name has a default value in your schema, we can safely fall back.
    bot_name = session.meta.bot_name or "the character"

    # 2. Filter using isinstance() to isolate TurnEntity types.
    #    Your IDE will now know exactly what properties exist on `c`
    turns = [c for c in session.children if isinstance(c, TurnEntity)]

    history = ""
    # Use the top 50 turns to establish names and personalities
    for turn in turns[:50]:
        role = "USER" if turn.actor_id == "user" else bot_name
        history += f"{role}: {turn.prose}\n"

    return history


def load_prompts() -> tuple[str, str]:
    """Loads system and user prompts from the local prompts package directory."""
    try:
        # 'steps.refine-characters.prompts' points to your text directory
        # python 3.9+ standard approach
        ref = importlib.resources.files("steps.refine-characters.prompts")
        system_prompt = (ref / "system.txt").read_text(encoding="utf-8")
        user_prompt_template = (ref / "user.txt").read_text(encoding="utf-8")
        return system_prompt.strip(), user_prompt_template.strip()
    except Exception as e:
        logger.error(f"Failed to load external prompt templates: {e}")
        raise


def run(config: dict) -> None:
    """LilaKosha Refinement Pass: Character Synthesis with robust parsing."""
    system_prompt, user_prompt_template = load_prompts()
    processed_vol = config["volumes"]["processed"]
    cdm_dir = os.path.join(processed_vol, "cdm")
    service_url = f"{config['services']['summarizer']}/v1/chat/completions"
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
    for i, line in enumerate(tqdm(lines, desc="Character Synthesis")):
        if not line.strip():
            continue
        session_dict = json.loads(line)
        session = Session.model_validate_json(line)
        bot_name = session.meta.bot_name
        chat_history = get_chat_history(session)
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt_template.format(chat_history=chat_history),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 2048,  # Increased to handle verbose reasoning content
            "response_format": {"type": "text"},
        }
        response_data = {}
        try:
            resp = requests.post(service_url, json=payload, timeout=120)
            resp.raise_for_status()
            response_data = resp.json()
            choices = response_data.get("choices", [])
            if choices:
                message_node = choices[0].get("message")
            else:
                logger.error("No choices returned in the response")
            raw_xml = message_node.get("content", "")
            reasoning = message_node.get("reasoning_content", "No reasoning provided")
            # Extract PC Name for console progression reporting
            pc_name = "Unknown"
            pc_match = re.search(
                r"<user_character>.*?<name>(.*?)</name>", raw_xml, re.DOTALL
            )
            if pc_match:
                pc_name = pc_match.group(1).strip()
            print(
                f" > [{i + 1}/{len(lines)}] Extracted: ",
                f"Bot({bot_name}), UserPC({pc_name})",
            )
            print(raw_xml)
            # CDM Enrichment
            session_dict["meta"]["character_synthesis_raw"] = raw_xml
            session_dict["meta"]["character_synthesis_reasoning"] = reasoning
            session_dict["meta"]["user_pc_name"] = pc_name
            # Insert synthesized data into the children as a "Character Detail" kind
            session_dict["children"].insert(
                1, {"kind": "character", "subkind": "detail", "content": raw_xml}
            )
        except (KeyError, TypeError, IndexError) as e:
            logger.error(f"Parsing failed for {bot_name}: {e}")
            print("\n" + "!" * 20 + " DEBUG: RAW JSON RESPONSE " + "!" * 20)
            print(
                json.dumps(response_data, indent=2)
                if response_data
                else "No JSON data."
            )
            print("!" * 66 + "\n")
        except Exception as e:
            logger.error(f"Critical error processing {bot_name}: {e}")
        updated_sessions.append(session_dict)
    # Physical Write to the Unified Ledger
    with open(latest_ledger, "w", encoding="utf-8") as f_out:
        for enriched_session in updated_sessions:
            f_out.write(json.dumps(enriched_session) + "\n")
    logger.info("✅ Character refinement complete.")
