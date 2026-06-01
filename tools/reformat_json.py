#!/usr/bin/env python3

import json
from pathlib import Path

import typer


def main(directory: Path):
    """Reformat JSON files with standard indentation and line-breaks."""
    json_files = directory.glob("*.json")
    if not json_files:
        print(f"No .json files found in the directory: {directory}")
        exit(1)

    for file_path in json_files:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        formatted_json = json.dumps(data, indent=2)
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(formatted_json + "\n")


if __name__ == "__main__":
    # The script will reformat files in the current working directory
    if __name__ == "__main__":
        typer.run(main)
