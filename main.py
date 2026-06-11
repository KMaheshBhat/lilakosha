import importlib
import logging
import sys

# Configure basic DX logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def load_config():
    # Placeholder: In a real run, this would parse your config.yaml
    # and provide the D: and E: mount paths to the steps.
    return {"paths": "validated"}


def main():
    config = load_config()
    requested_steps = sys.argv[1:]

    if not requested_steps:
        logging.info("Usage: uv run main.py <step1> <step2> ...")
        logging.info("Available steps: prepare, train, bake")
        return

    # VRAM Handover Warning for array execution
    if len(requested_steps) > 1 and "train" in requested_steps:
        print("\n!!! VRAM HANDOVER WARNING !!!")
        print("Array execution detected. Ensure llama-server is TERMINATED")
        print("before the 'train' step begins to free the 8.4GB buffer.\n")

    for step_name in requested_steps:
        try:
            # Dynamically look for steps.{step_name}
            step_module = importlib.import_module(f"steps.{step_name}")
            logging.info(f"--- Executing Step: {step_name.upper()} ---")

            # Every step directory must have a run() function in its __init__.py
            step_module.run(config)

        except ImportError:
            logging.error(f"Step '{step_name}' not found in steps/ directory.")
        except AttributeError:
            logging.error(f"Step '{step_name}' has no run() function.")
        except Exception as e:
            logging.error(f"Critical failure in {step_name}: {e}")
            break  # Halt the array if a step fails


if __name__ == "__main__":
    main()
