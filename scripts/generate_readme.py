#!/usr/bin/env python3
"""Generate README.md sections from code definitions.

This script updates sections of README.md marked with AUTO-GENERATED comments.
Run it after adding/modifying commands to keep documentation in sync.

Usage:
    python scripts/generate_readme.py
"""
import re
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sc2_replay_analyzer.commands import FILTER_COMMANDS, SIMPLE_COMMANDS
from sc2_replay_analyzer.config import AVAILABLE_COLUMNS


def generate_filter_commands_table() -> str:
    """Generate markdown table for filter commands."""
    lines = [
        "| Command | Description | Example |",
        "|---------|-------------|---------|",
    ]

    for cmd_def in FILTER_COMMANDS.values():
        # Use display_text which shows "short, long" format
        command = f"`{cmd_def.display_text}`"
        description = cmd_def.description
        example = f"`{cmd_def.example}`"
        lines.append(f"| {command} | {description} | {example} |")

    # Add simple commands
    for key, (name, desc) in SIMPLE_COMMANDS.items():
        if key in ("columns", "clear", "help", "quit"):
            lines.append(f"| `{name}` | {desc} | |")

    return "\n".join(lines)


def generate_available_columns() -> str:
    """Generate list of available columns."""
    columns = sorted(AVAILABLE_COLUMNS.keys())
    return "`" + "`, `".join(columns) + "`"


def update_readme():
    """Update README.md with auto-generated sections."""
    readme_path = Path(__file__).parent.parent / "README.md"
    content = readme_path.read_text()

    # Define section generators
    sections = {
        "FILTER_COMMANDS": generate_filter_commands_table,
        "AVAILABLE_COLUMNS": generate_available_columns,
    }

    # Replace each section
    for section_name, generator in sections.items():
        pattern = rf"(<!-- AUTO-GENERATED: {section_name} -->\n).*?(\n<!-- END AUTO-GENERATED -->)"
        replacement = rf"\1{generator()}\2"
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    readme_path.write_text(content)
    print(f"Updated {readme_path}")

    # Show what was generated
    for section_name, generator in sections.items():
        print(f"\n{section_name}:")
        print(generator()[:200] + "..." if len(generator()) > 200 else generator())


if __name__ == "__main__":
    update_readme()
