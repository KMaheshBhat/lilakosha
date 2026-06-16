import importlib
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import yaml

# Configure professional DX logging for Operator oXperience (OX)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def interpolate_env_vars(node: Any) -> Any:
    """Recursively resolves ${VAR} or $VAR within the config dictionary."""
    if isinstance(node, str):
        return re.sub(
            r"\$(\w+)|\${(\w+)}",
            lambda m: os.getenv(m.group(1) or m.group(2), m.group(0)),
            node,
        )
    elif isinstance(node, dict):
        return {k: interpolate_env_vars(v) for k, v in node.items()}
    elif isinstance(node, list):
        return [interpolate_env_vars(x) for x in node]
    return node


def load_config(config_path: Path) -> dict[str, Any]:
    """Loads YAML and validates the resolution of LilaKosha Volumes and Services."""
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Cast to dict[str, Any] for type-checking noise reduction (LSP)
    resolved_config = cast(dict[str, Any], interpolate_env_vars(config))

    # Pre-flight check for unresolved environment variables
    # Validates $LILAKOSHA_VOLUME_* and $LILAKOSHA_SERVICE_*
    for section in ["volumes", "services"]:
        data = resolved_config.get(section, {})
        for key, value in data.items():
            if isinstance(value, str) and ("$" in value or value == ""):
                logger.error(
                    f"UNRESOLVED {section.upper()}: '{key}' is missing or invalid. "
                    f"Ensure you have exported the "
                    f"LILAKOSHA_{section[:-1].upper()}_* variable."
                )
                sys.exit(1)

    return resolved_config


def list_available_resources() -> list[str]:
    """Discovers configs for enhanced Operator Experience (OX)."""
    config_dir = Path("pipeline")
    if config_dir.exists() and config_dir.is_dir():
        return sorted(
            [f.name for f in config_dir.glob("*") if f.suffix in (".yaml", ".yml")]
        )
    return []


def main() -> None:
    # Discover resources for help screen or validation
    configs = list_available_resources()

    # Operator Help / Resource Discovery
    if len(sys.argv) < 2:
        help_block = (
            f"\n{'=' * 65}\n"
            f"🛠️  LILAKOSHA FLOW MK1: CONFIG-DRIVEN ORCHESTRATOR\n"
            f"{'=' * 65}\n\n"
            f"Usage: uv run main.py <config_path>\n\n"
            f"Discovered Pipeline Configurations ({len(configs)}):\n"
        )
        for cfg in configs:
            help_block += f"  - pipeline/{cfg}\n"

        help_block += (
            f"\nExecution Workflow Examples:\n"
            f"  uv run main.py pipeline/init.yml\n"
            f"  uv run main.py pipeline/prepare.yml\n"
            f"  uv run main.py pipeline/train-and-bake-lilakosha-1g-12b-u.yml\n"
            f"{'=' * 65}\n"
        )
        logger.info(help_block)
        return

    config_path = Path(sys.argv[1])

    # 1. Load configuration and determine the pipeline sequence
    config = load_config(config_path)
    pipeline = config.get("pipeline", [])
    if not pipeline:
        logger.error(f"No 'pipeline' steps defined in {config_path}.")
        sys.exit(1)

    # 2. Metadata Extraction for High-Level Tracking
    project = config.get("project", {})
    project_name = project.get("name", "LilaKosha")
    logger.info(f"Target Project: {project_name}")
    logger.info(f"Pipeline Sequence: {pipeline}")

    # 3. VRAM Handover Warning (Triggered when explicit training keys are in play)
    if "train" in pipeline:
        warning_block = (
            "\n!!! VRAM HANDOVER WARNING !!!\n"
            "Executing hardware-intensive training workflow "
            "on 12GB VRAM resource pool.\n"
            "Ensure ALL inference backend services "
            "are TERMINATED before training begins.\n"
        )
        logger.warning(warning_block)

    # 4. Sequential Execution Loop
    for step_name in pipeline:
        try:
            # Dynamically import the step module from the 'steps/' directory
            step_module = importlib.import_module(f"steps.{step_name}")
            logger.info(f"--- Executing Step: {step_name.upper()} ---")

            # Execute the step with the resolved config
            step_module.run(config)
        except ImportError:
            logger.error(
                f"Step implementation for '{step_name}' not found in steps/ folder."
            )
            break
        except Exception as e:
            logger.exception(f"Critical failure in step '{step_name}': {e}")
            break  # Halt the pipeline sequence on failure


if __name__ == "__main__":
    main()
