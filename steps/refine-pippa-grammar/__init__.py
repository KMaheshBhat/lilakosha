import importlib.resources
import logging
import time
from pathlib import Path

from jinja2 import BaseLoader, Environment
from tqdm import tqdm

from cdm.core import ContentVariant, Document, TurnItem
from cdm.meta import add_annotation, has_annotation, update_meta
from cdm.refine import SingleTurnGrammarResponse
from inference import Message, OpenAIInference

logger = logging.getLogger(__name__)


class InferenceBudgetExhausted(Exception):
    """Internal exception to cleanly unwind nested turn/record loops."""

    pass


def load_jinja_templates(templates: list[str]) -> dict[str, str]:
    """Loads raw templates from the package directory."""
    try:
        result = {}
        ref = importlib.resources.files("steps.refine-pippa-grammar.templates")
        for template in templates:
            template_str = (ref / f"{template}.jinja2").read_text(
                encoding="utf-8"
            )
            result[template] = template_str.strip()
        return result
    except Exception as e:
        logger.error(f"Failed to load external grammar prompt templates: {e}")
        raise


def get_variant_text(item: TurnItem, variant_name: str) -> str | None:
    """Helper to extract variant text by name from a TurnItem."""
    for variant in item.content:
        if variant.name == variant_name:
            return variant.text
    return None


def run(config: dict) -> None:
    """
    LilaKosha Refinement Pass: Single-Turn Grammar Revision (PIPPA).
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
            f"🎯 Targeted Refinement Scope Activated (PIPPA Grammar):\n"
            f"    - Start Boundary: {start_uuid or '[-∞ Unbound]'}\n"
            f"    - Stop Boundary:  {stop_uuid or '[+∞ Unbound]'}"
        )
    else:
        logger.info(
            "🔬 Refinement Scope: Global Sweep (No parameters provided)"
        )

    logger.info(
        f"Inspecting {len(record_files)} records for PIPPA grammar processing..."
    )

    CONTEXT_WINDOW_SIZE = 5

    skipped_range_count = 0
    binding = config["bindings"]["refine-pippa-grammar"]
    service = config["services"][binding["service"]]
    temperature = binding.get("temperature", 0.3)
    inference = OpenAIInference.from_service(service)
    requests_per_minute = service.get("requests_per_minute")
    allows_think_control = service.get("allows_think_control", True)
    allows_extra_body = service.get("allows_extra_body", True)
    next_request_time: float | None = None
    max_inference_budget = binding.get("max_inference_budget")
    inference_counter = 0

    try:
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
                    document = Document.model_validate_json(f.read())

                history_turns = []

                # Iterate through tracking transaction items
                progress_desc = f" → {file_path.name[:12]}..."
                for item in tqdm(
                    document.items, desc=progress_desc, leave=False
                ):
                    if not isinstance(item, TurnItem):
                        continue

                    # Idempotency / state check using ContentVariants
                    has_orig = any(v.name == "original" for v in item.content)
                    has_ref = any(
                        v.name == "refine-pippa-grammar" for v in item.content
                    )

                    if has_orig and has_ref:
                        history_turns.append(item)
                        continue

                    try:
                        # 1. Budget Boundary Verification
                        if (
                            max_inference_budget
                            and inference_counter >= max_inference_budget
                        ):
                            raise InferenceBudgetExhausted()

                        history_context = history_turns[
                            -CONTEXT_WINDOW_SIZE:
                        ]

                        # Render context parameters passing layout to templates
                        user_prompt = user_tmpl.render(
                            session=document,
                            target_turn=item,
                            history_context=history_context,
                        )
                        system_prompt = system_tmpl.render(session=document)

                        # Extract target text for token estimation
                        current_text = (
                            get_variant_text(item, "refine-pippa-grammar")
                            or get_variant_text(item, "original")
                            or (
                                item.content[0].text if item.content else ""
                            )
                        )

                        # Estimate raw token overhead (1 word ≈ 1.3 tokens)
                        est_input_tokens = int(
                            len(current_text.split()) * 1.3
                        )

                        # Establish a baseline floor of 8192 tokens
                        unbound_max_tokens = max(
                            8192, int(est_input_tokens * 3.0)
                        )

                        if (
                            requests_per_minute
                            and next_request_time is not None
                        ):
                            now = time.monotonic()
                            if now < next_request_time:
                                time.sleep(next_request_time - now)

                        extra_body_payload = (
                            {"thinking_budget_tokens": 0}
                            if allows_extra_body
                            else {}
                        )
                        reasoning_effort = (
                            "none" if allows_think_control else None
                        )

                        try:
                            result = inference.generate(
                                messages=[
                                    Message.system(system_prompt),
                                    Message.user(user_prompt),
                                ],
                                response_model=SingleTurnGrammarResponse,
                                temperature=temperature,
                                max_tokens=unbound_max_tokens,
                                reasoning_effort=reasoning_effort,
                                extra_body=extra_body_payload,
                            )
                        finally:
                            # 2. Increment Inference Allocation
                            inference_counter += 1
                            if requests_per_minute:
                                interval = 60.0 / requests_per_minute
                                next_request_time = time.monotonic() + interval

                        extracted_data = result.value
                        reasoning = result.reasoning
                        logger.debug(f"extracted_data: {extracted_data}")

                        # Update turn state inline using ContentVariant lineage
                        if not has_orig:
                            initial_text = (
                                item.content[0].text if item.content else ""
                            )
                            item.content.append(
                                ContentVariant(
                                    name="original", text=initial_text
                                )
                            )

                        # Update or insert refine-pippa-grammar variant
                        refined_variant = next(
                            (
                                v
                                for v in item.content
                                if v.name == "refine-pippa-grammar"
                            ),
                            None,
                        )
                        rewritten = extracted_data.rewritten_prose
                        if refined_variant:
                            refined_variant.text = rewritten
                        else:
                            item.content.append(
                                ContentVariant(
                                    name="refine-pippa-grammar",
                                    text=rewritten,
                                )
                            )

                        # Append tracking step annotation if not present
                        if not has_annotation(document, "refine-pippa-grammar"):
                            add_annotation(
                                document,
                                kind="refine-pippa-grammar",
                                content="step-by-step single-turn third-person",
                                reasoning=reasoning,
                            )

                        # Re-materialize layout metric statistics post-mutation
                        update_meta(document)

                        # Flush state to flat file post-mutation
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(
                                document.model_dump_json(
                                    indent=2, by_alias=True
                                )
                            )

                    except InferenceBudgetExhausted:
                        raise
                    except Exception as turn_err:
                        logger.error(
                            f"Skipping corrupted turn generation for item in "
                            f"{file_path.name}: {turn_err}"
                        )
                        continue

                    history_turns.append(item)

            except InferenceBudgetExhausted:
                raise
            except Exception as e:
                logger.error(
                    f"Failed step-by-step grammar pass for canvas "
                    f"document {file_path.name}: {e}"
                )

    except InferenceBudgetExhausted:
        logger.info(
            f"🛑 Inference quota budget fully consumed "
            f"({max_inference_budget}/{max_inference_budget} requests allocation). "
            f"Gracefully terminating execution loops to conserve pipeline cycles."
        )

    logger.info(
        f"✅ Step-by-step grammar refinement script pass finished. "
        f"Skipped out-of-range: {skipped_range_count} records. "
        f"Total calls executed: {inference_counter}."
    )
