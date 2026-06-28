import importlib.resources
import logging
import time
from pathlib import Path

from jinja2 import BaseLoader, Environment
from tqdm import tqdm

from cdm.core import Annotation, Session, TurnItem
from cdm.refine import SingleTurnGrammarResponse
from inference import Message, OpenAIInference

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

    # Extract and Validate Target Range Markers
    params = config.get("parameters", {})
    start_uuid = params.get("start_uuid")
    stop_uuid = params.get("stop_uuid")

    if start_uuid or stop_uuid:
        logger.info(
            f"🎯 Targeted Refinement Scope Activated (Grammar):\n"
            f"   - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"   - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )
    else:
        logger.info(
            "🔬 Refinement Scope: Global Sweep (No lexical range parameters provided)"
        )

    logger.info(
        f"Inspecting {len(record_files)} records for granular grammar processing..."
    )

    CONTEXT_WINDOW_SIZE = 5

    skipped_range_count = 0
    binding = config["bindings"]["refine-grammar"]
    service = config["services"][binding["service"]]
    temperature = binding.get("temperature", 0.3)
    inference = OpenAIInference.from_service(service)
    execution = binding.get("execution", {})
    requests_per_minute = execution.get("requests_per_minute")
    next_request_time: float | None = None

    for file_path in tqdm(record_files, desc="Processing Canvas Files"):
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
            with open(file_path, "r", encoding="utf-8") as f:
                session = Session.model_validate_json(f.read())

            # --- Health Guard Gate ---
            # Skip if a previous telemetry pass explicitly identified
            # this file as defective
            if session.meta and session.meta.healthy is False:
                continue

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

                    if requests_per_minute and next_request_time is not None:
                        now = time.monotonic()
                        if now < next_request_time:
                            logger.debug("Rate limiting: sleeping before request")
                            time.sleep(next_request_time - now)
                    result = inference.generate(
                        messages=[
                            Message.system(system_prompt),
                            Message.user(user_prompt),
                        ],
                        response_model=SingleTurnGrammarResponse,
                        temperature=temperature,
                        max_tokens=unbound_max_tokens,
                        reasoning_effort="none",
                        extra_body={
                            "thinking_budget_tokens": 0,
                        },
                    )
                    if requests_per_minute:
                        next_request_time = time.monotonic() + (
                            60.0 / requests_per_minute
                        )
                    extracted_data = result.value
                    reasoning = result.reasoning
                    logger.debug(f"extracted_data: {extracted_data}")

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
                            reasoning=reasoning,
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

    logger.info(
        f"✅ Step-by-step grammar refinement script pass finished. "
        f"Skipped out-of-range: {skipped_range_count} records."
    )
