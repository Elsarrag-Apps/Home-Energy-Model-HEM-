#!/usr/bin/env python3
"""Check for direct floating-point comparisons with 0.0."""

import ast
import sys
from pathlib import Path


def check_file(filepath: Path) -> list[str]:
    """Check a single Python file for float comparison issues."""
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.splitlines()
        tree = ast.parse(content, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError) as e:
        return [f"{filepath}: Failed to parse: {e}"]

    issues = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for op, comparator in zip(node.ops, node.comparators, strict=False):
                # Check for == 0.0 or != 0.0
                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, float):
                    if comparator.value == 0.0 and isinstance(op, (ast.Eq, ast.NotEq)):  # noqa: float-compare
                        # Check for noqa comment on the same line
                        line_idx = node.lineno - 1
                        if line_idx < len(lines) and "# noqa: float-compare" in lines[line_idx]:
                            continue

                        op_symbol = "==" if isinstance(op, ast.Eq) else "!="
                        issues.append(
                            f"{filepath}:{node.lineno}:{node.col_offset}: "
                            f"Direct float comparison '{op_symbol} 0.0' detected. "
                            f"Use math.isclose(..., 0.0, abs_tol=1e-10) instead"
                        )

    return issues


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: check_float_compare.py <file1.py> [file2.py ...]", file=sys.stderr)
        return 1

    all_issues = []
    for filepath_str in sys.argv[1:]:
        filepath = Path(filepath_str)
        if filepath.suffix == ".py":
            issues = check_file(filepath)
            all_issues.extend(issues)

    if all_issues:
        print("\nFloat comparison issues found:\n", file=sys.stderr)
        for issue in all_issues:
            print(f"  {issue}", file=sys.stderr)
        print(
            "\nHow to fix:",
            file=sys.stderr,
        )
        print("  Replace direct comparisons with math.isclose():", file=sys.stderr)
        print("  - '== 0.0' -> 'math.isclose(value, 0.0, abs_tol=1e-10)'", file=sys.stderr)
        print(
            "  - '!= 0.0' -> 'not math.isclose(value, 0.0, abs_tol=1e-10)'",
            file=sys.stderr,
        )
        print(
            "\n  If the comparison is intentional (e.g., checking explicit input values,",
            file=sys.stderr,
        )
        print(
            "  test assertions, or sentinel values), add '# noqa: float-compare' to the line.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
