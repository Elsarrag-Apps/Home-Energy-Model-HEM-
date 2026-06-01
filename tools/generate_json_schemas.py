from pathlib import Path

from hem_core.schema_utils import write_schema_files

PATH_ROOT = Path(__file__).parent.parent
PATH_SCHEMAS = PATH_ROOT / "schemas"


if __name__ == "__main__":
    write_schema_files(schema_path=PATH_SCHEMAS)
