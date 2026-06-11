import importlib
import logging
import os
import re
import sys
from typing import Any, cast

import yaml

# Configure professional DX logging
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
    """Loads and interpolates the YAML config for the target variant."""
    if not os.path.exists(config_path):
        logging.error(f"Config file not found: {config_path}")
        sys.exit(1)
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    # Cast to dict[str, Any] to satisfy basedpyright LSP
    resolved_config = cast(dict[str, Any], interpolate_env_vars(config))
    # Pre-flight check for infrastructure variables
    infrastructure = resolved_config.get("infrastructure", {})
    for key, value in infrastructure.items():
        if isinstance(value, str) and "$" in value:
            logging.error(f"Missing Env Var: {value} was not resolved.")
            sys.exit(1)
    return resolved_config


def list_available_resources():
    """Discovers steps and configs for enhanced Operator Experience (OX)."""
    steps_dir = "steps"
    config_dir = "config"
    available_steps = []
    if os.path.exists(steps_dir):
        available_steps = [
            d
            for d in os.listdir(steps_dir)
            if os.path.isdir(os.path.join(steps_dir, d)) and not d.startswith("__")
        ]
    available_configs = []
    if os.path.exists(config_dir):
        available_configs = [
            f for f in os.listdir(config_dir) if f.endswith((".yaml", ".yml"))
        ]
    return sorted(available_configs), sorted(available_steps)


def main():
    # Discover resources for help screen or validation
    configs, steps = list_available_resources()
    # Special Case: Allow 'stage' to run without a configuration file
    if len(sys.argv) == 2 and sys.argv[1] == "stage":
        logging.info("--- Executing Step: STAGE (Config-Less Bootstrap) ---")
        try:
            step_module = importlib.import_module("steps.stage")
            step_module.run(None)
            return
        except Exception as e:
            logging.error(f"Critical failure in infrastructure staging: {e}")
            sys.exit(1)

    # Normal Case: Expecting uv run main.py <config_path> <step1> ...
    if len(sys.argv) < 3:
        print("\n" + "=" * 65)
        print("🛠️  LILAKOSHA FLOW MK1: PIPELINE ORCHESTRATOR")
        print("=" * 65)
        print("\nUsage (Standard): uv run main.py <config_path> <step1> [step2] ...")
        print("Usage (Bootstrap): uv run main.py stage")
        print(f"\nDiscovered Configurations ({len(configs)}):")
        for cfg in configs:
            print(f"  - config/{cfg}")
        print(f"\nDiscovered Pipeline Steps ({len(steps)}):")
        for step in steps:
            print(f"  - {step}")
        print("\nExample Commands:")
        print("  uv run main.py stage")
        if configs:
            print(f"  uv run main.py config/{configs} prepare train")
        print("=" * 65 + "\n")
        return

    config_path = sys.argv[1]
    requested_steps = sys.argv[2:]
    # 1. Load configuration for the target flavor
    config = load_config(config_path)
    # 2. Extract Flavor Metadata for Logging
    # Fixed nesting: model_variant is inside the 'project' block
    project = config.get("project", {})
    variant = project.get("model_variant", "unknown").upper()
    logging.info(f"Loaded {project.get('name')} {project.get('mark')} configuration.")
    logging.info(f"Target Generation: {project.get('generation')} | Flavor: {variant}")
    # 3. OX Validation: Ensure steps exist
    for step_name in requested_steps:
        if step_name not in steps:
            logging.error(f"Step '{step_name}' not found. Check 'steps/' directory.")
            sys.exit(1)
    # 4. VRAM Handover Warning
    if "train" in requested_steps:
        print("\n!!! VRAM HANDOVER WARNING !!!")
        print(f"Training the {variant} variant requires the full 12GB buffer.")
        print("Ensure llama-server is TERMINATED before training begins.\n")
    # 5. Dynamic Execution Loop
    for step_name in requested_steps:
        try:
            step_module = importlib.import_module(f"steps.{step_name}")
            logging.info(f"--- Executing Step: {step_name.upper()} ({variant}) ---")
            step_module.run(config)
        except Exception as e:
            logging.error(f"Critical failure in step '{step_name}': {e}")
            break


if __name__ == "__main__":
    main()
