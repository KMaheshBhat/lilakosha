import logging
import os
from typing import Any, cast

# Configure internal step logging
logger = logging.getLogger(__name__)


def run(_config: dict[str, Any] | None = None) -> None:
    """
    LilaKosha-Flow-MK1 Infrastructure Staging.

    This step bootstraps the folder architecture across D: and E: mounts
    using environment variables and provides manual acquisition logs.
    """
    # 1. Retrieve Environment Variables (narrowing from str | None to str)
    env_data = os.getenv("LILAKOSHA_BASE_DATA")
    env_process = os.getenv("LILAKOSHA_BASE_PROCESS_DIR")
    env_models = os.getenv("LILAKOSHA_BASE_MODEL_BASE_DIR")
    env_export = os.getenv("LILAKOSHA_BASE_EXPORT_DIR")
    # 2. Critical Type Guard: Halt if paths are missing
    if not all([env_data, env_process, env_models, env_export]):
        missing = [
            k
            for k, v in {
                "LILAKOSHA_BASE_DATA": env_data,
                "LILAKOSHA_BASE_PROCESS_DIR": env_process,
                "LILAKOSHA_BASE_MODEL_BASE_DIR": env_models,
                "LILAKOSHA_BASE_EXPORT_DIR": env_export,
            }.items()
            if v is None
        ]
        logger.error("STAGING FAILED: Missing environment variables.")
        print(f"\nPlease export the following in your shell:\n{missing}")
        return
    # 3. Cast to 'str' to eliminate 'StrPath' linting errors in Zed
    base_data = cast(str, env_data)
    base_process = cast(str, env_process)
    base_models = cast(str, env_models)
    base_export = cast(str, env_export)
    print(f"\n{'=' * 65}")
    print("🛠️  LILAKOSHA MK1: INFRASTRUCTURE STAGING")
    print(f"{'=' * 65}")
    # 4. Define Flavor-Isolated Tree (Pillars: G vs U Isolation)
    paths_to_create = [
        # Raw Data landing zones
        os.path.join(base_data, "raw/general"),
        os.path.join(base_data, "raw/unbound"),
        # Processed Data (Stage 1 Output)
        os.path.join(base_process, "general_chunks"),
        os.path.join(base_process, "unbound_chunks"),
        # Model Repository (156GB D: Drive preference)
        os.path.join(base_models, "google/gemma-4-12b-it"),
        os.path.join(base_models, "OpenYourMind/gemma-4-12b-it-abliterated-uncensored"),
        os.path.join(base_models, "checkpoints"),
        # Export Destination (352GB E: Drive preference)
        os.path.join(base_export, "gguf_builds/general"),
        os.path.join(base_export, "gguf_builds/unbound"),
    ]
    for path in paths_to_create:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            print(f"  [CREATED] {path}")
        else:
            print(f"  [EXISTS ] {path}")
    # 5. Operator Instructions for Model Acquisition [1, 2]
    print(f"\n{'-' * 65}")
    print("📥 MODEL ACQUISITION & PLACEMENT")
    print(f"{'-' * 65}")
    print("\n1. GENERAL VARIANT (Safe/SFW Foundation):")
    print("   > Download: https://huggingface.co/google/gemma-4-12b-it")
    print(f"   > Place in: {os.path.join(base_models, 'google/gemma-4-12b-it')}")
    print("\n2. UNBOUND VARIANT (Abliterated/Uncensored Foundation):")
    print(
        "   > Download: https://huggingface.co/OpenYourMind/gemma-4-12b-it-abliterated-uncensored"
    )
    ub = os.path.join(base_models, "OpenYourMind/gemma-4-12b-it-abliterated-uncensored")
    print(f"   > Place in: {ub}")
    print("\n3. DATA STAGING:")
    print("   > Place PIPPA or MUCE raw logs in the 'raw/unbound' sub-folder.")
    print("   > Misplaced files will 'stick out like a sore thumb' .")
    print(f"\n{'=' * 65}")
    print("✅ Infrastructure is staged for LilaKosha-G1.")
    print(f"{'=' * 65}\n")
