import importlib.resources
import logging
from pathlib import Path

import requests
from jinja2 import BaseLoader, Environment
from tqdm import tqdm

from cdm.core import Annotation, Session, TurnItem
from cdm.refine import SingleTurnGrammarResponse

logger = logging.getLogger(__name__)


def load_jinja_templates(templates: list[str]) -> dict[str, str]:
    """Loads raw templates from the package directory."""
    try:
        result = {}
        ref = importlib.resources.files("steps.refine-grammar.templates")
        for template in templates:
            template_str = (ref / f"{template}.jinja2").read_text(encoding="utf-8")
            result[template] = template_str.strip()
        return result
    except Exception as e:
        logger.error(f"Failed to load external grammar prompt templates: {e}")
        raise


def run(config: dict) -> None:
    """
    LilaKosha Refinement Pass: Single-Turn Grammar Revision.
    Iterates through standalone canvas documents, evaluating and rewriting unrefined
    turns one-by-one into a third-person, past-tense novelistic prose format.
    """
    templates_str = load_jinja_templates(["system", "user"])
    jinja_env = Environment(loader=BaseLoader())
    user_tmpl = jinja_env.from_string(templates_str["user"])
    system_tmpl = jinja_env.from_string(templates_str["system"])

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

    logger.info(
        f"Inspecting {len(record_files)} records for granular grammar processing..."
    )
    service_url = f"{config['services']['grammar']}/v1/chat/completions"

    CONTEXT_WINDOW_SIZE = 5

    for file_path in tqdm(record_files, desc="Processing Canvas Files"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                session = Session.model_validate_json(f.read())

            history_turns = []

            # Swap from legacy session.children to the compliant
            # transaction session.items
            for item in tqdm(
                session.items, desc=f" → {file_path.name[:12]}...", leave=False
            ):
                if not isinstance(item, TurnItem):
                    continue

                if item.original_prose is not None:
                    history_turns.append(item)
                    continue

                try:
                    history_context = history_turns[-CONTEXT_WINDOW_SIZE:]

                    user_prompt = user_tmpl.render(
                        session=session,
                        target_turn=item,
                        history_context=history_context,
                    )
                    system_prompt = system_tmpl.render(session=session)

                    # Calculate raw token overhead (roughly 1 word ≈ 1.3 tokens)
                    estimated_input_tokens = int(len(item.prose.split()) * 1.3)

                    # Establish a massive baseline floor of 8192 tokens to protect
                    # the target engine's reasoning budget.
                    unbound_max_tokens = max(8192, int(estimated_input_tokens * 3.0))

                    payload = {
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": unbound_max_tokens,
                        "thinking_budget_tokens": 0,
                        "response_format": {
                            "type": "json_object",
                            "schema": SingleTurnGrammarResponse.model_json_schema(),
                        },
                    }
                    resp = requests.post(service_url, json=payload, timeout=240)
                    resp.raise_for_status()

                    # 1. Parse the top-level API envelope
                    resp_json = resp.json()

                    # 2. Extract the finish reason from the choices payload
                    choices = resp_json.get("choices", [{}])
                    finish_reason = (
                        choices[0].get("finish_reason", "stop") if choices else "stop"
                    )

                    # 3. Extract the actual text string containing the JSON structure
                    raw_content = (
                        choices[0].get("message", {}).get("content", "{}")
                        if choices
                        else "{}"
                    )

                    # 4. Handle token truncation safely via logger instead of bare print
                    if finish_reason == "length":
                        logger.warning(
                            f"Generation cut off by token limit for item in "
                            f"{file_path.name} "
                            f"(finish_reason: length)"
                        )

                    # 5. Fall through to standard validation if it finished normally
                    extracted_data = SingleTurnGrammarResponse.model_validate_json(
                        raw_content
                    )

                    # Update turn state inline
                    item.original_prose = item.prose
                    item.prose = extracted_data.rewritten_prose

                    # Append tracking step annotation if not present for this run phase
                    has_annotation = any(
                        anno.kind == "refine-grammar"
                        for anno in (session.meta.annotations or [])
                    )
                    if not has_annotation:
                        grammar_annotation = Annotation(
                            kind="refine-grammar",
                            content="step-by-step single-turn third-person",
                            reasoning=None,
                        )
                        if not session.meta.annotations:
                            session.meta.annotations = []
                        session.meta.annotations.append(grammar_annotation)

                    # Flush state to flat file immediately after single turn success
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(session.model_dump_json(indent=2))

                except Exception as turn_err:
                    logger.error(
                        f"Skipping corrupted turn generation for item in "
                        f"{file_path.name}: {turn_err}"
                    )
                    continue

                history_turns.append(item)

        except Exception as e:
            logger.error(
                f"Failed step-by-step grammar pass for canvas "
                f"document {file_path.name}: {e}"
            )

    logger.info("✅ Step-by-step grammar refinement script pass finished.")
