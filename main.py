import importlib
import logging
import os
import re
import sys
from typing import Any, cast

import yaml

# Configure professional DX logging for Operator oXperience (OX)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


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


def load_config(config_path: str) -> dict[str, Any]:
    """Loads YAML and validates the resolution of LilaKosha Volumes and Services."""
    if not os.path.exists(config_path):
        logging.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Cast to dict[str, Any] for type-checking noise reduction (LSP)
    resolved_config = cast(dict[str, Any], interpolate_env_vars(config))

    # Pre-flight check for unresolved environment variables
    # Validates $LILAKOSHA_VOLUME_* and $LILAKOSHA_SERVICE_* [User Input]
    for section in ["volumes", "services"]:
        data = resolved_config.get(section, {})
        for key, value in data.items():
            if isinstance(value, str) and ("$" in value or value == ""):
                logging.error(
                    f"UNRESOLVED {section.upper()}: '{key}' is missing or invalid. "
                    "Ensure you have exported the "
                    f"LILAKOSHA_{section[:-1].upper()}_* variable."
                )
                sys.exit(1)

    return resolved_config


def list_available_resources():
    """Discovers configs for enhanced Operator Experience (OX)."""
    config_dir = "config"
    available_configs = []
    if os.path.exists(config_dir):
        available_configs = [
            f for f in os.listdir(config_dir) if f.endswith((".yaml", ".yml"))
        ]
    return sorted(available_configs)


def main():
    # Discover resources for help screen or validation
    configs = list_available_resources()
    # Operator Help / Resource Discovery
    if len(sys.argv) < 2:
        print("\n" + "=" * 65)
        print("🛠️  LILAKOSHA FLOW MK1: CONFIG-DRIVEN ORCHESTRATOR")
        print("=" * 65)
        print("\nUsage: uv run main.py <config_path>")
        print(f"\nDiscovered Pipeline Configurations ({len(configs)}):")
        for cfg in configs:
            print(f"  - config/{cfg}")
        print("\nExecution Workflow Examples:")
        print("  uv run main.py config/stage.yml")
        print("  uv run main.py config/prepare.yml")
        print("  uv run main.py config/train-and-bake-lilakosha-1g-12b-u.yml")
        print("=" * 65 + "\n")
        return
    config_path = sys.argv[1]
    # 1. Load configuration and determine the specific pipeline flavor
    config = load_config(config_path)
    pipeline = config.get("pipeline", [])
    if not pipeline:
        logging.error(f"No 'pipeline' steps defined in {config_path}.")
        sys.exit(1)
    # 2. Metadata Extraction for Flavor-Aware Logging
    project = config.get("project", {})
    variant = project.get("model_variant", "infrastructure").upper()
    logging.info(f"Target: {project.get('name', 'LilaKosha')} | Variant: {variant}")
    logging.info(f"Pipeline: {pipeline}")
    # 3. VRAM Handover Warning (Specific to 12GB hardware limit)
    if "train" in pipeline:
        print("\n!!! VRAM HANDOVER WARNING !!!")
        print(f"Executing {variant} training on 12GB VRAM.")
        print("Ensure ALL inference services are TERMINATED before training begins.\n")
    # 4. Sequential Execution Loop
    for step_name in pipeline:
        try:
            # Dynamically import the step module from the 'steps/' directory
            step_module = importlib.import_module(f"steps.{step_name}")
            logging.info(f"--- Executing Step: {step_name.upper()} ({variant}) ---")
            # Execute the step with the resolved config
            step_module.run(config)
        except ImportError:
            logging.error(
                f"Step implementation for '{step_name}' not found in steps/ folder."
            )
            break
        except Exception as e:
            logging.error(f"Critical failure in step '{step_name}': {e}")
            break  # Halt the pipeline sequence on failure


if __name__ == "__main__":
    main()
