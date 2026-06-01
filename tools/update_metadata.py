import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PATH_ROOT = Path(__file__).parent.parent
PATH_TEST = PATH_ROOT / "test"
PATH_TEST_E2E = PATH_TEST / "e2e"
PATH_DEMO_FILES = PATH_TEST_E2E / "demo_files"


def _update_all_demo_files_metadata(version: str):
    for sub_path in PATH_DEMO_FILES.iterdir():
        if sub_path.is_dir():
            for filepath in sub_path.glob("*.json"):
                _update_file_metadata(filepath=filepath, version=version)


def _update_file_metadata(filepath: Path, version: str):
    try:
        with open(filepath, "r") as file:
            demo_data: dict[str, Any] = json.load(file)

        if "metadata" not in demo_data:
            logger.warning(f"Skipping {filepath.name}: 'metadata' key not found.")
            return

        demo_data["metadata"]["hem_core_version"] = version
        with open(filepath, "w") as file:
            json.dump(demo_data, file, indent=4, ensure_ascii=False)

    except json.JSONDecodeError:
        logger.error(f"Skipping {filepath.name}: Not a valid JSON file.")
    except Exception as e:
        logger.error(f"Error processing {filepath.name}: {e}")


def main(args: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "version",
        action="store",
        help="new core engine version",
    )
    cli_args = parser.parse_args(args)

    _update_all_demo_files_metadata(version=cli_args.version)


if __name__ == "__main__":
    sys.exit(main())
