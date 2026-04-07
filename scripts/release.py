#!/usr/bin/env python3
"""Create a new release by bumping version, updating changelog, committing, and tagging."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Literal, cast

BumpPart = Literal["major", "minor", "patch"]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"
CHANGELOG_FILE = PROJECT_ROOT / "CHANGELOG.rst"
UV_LOCK_FILE = PROJECT_ROOT / "uv.lock"
PROJECT_NAME = "postgresql-notification-listener"

VERSION_PATTERN = re.compile(
    r'^(version\s*=\s*")(?P<version>\d+\.\d+\.\d+)("\s*)$', re.MULTILINE
)
UV_LOCK_VERSION_PATTERN = re.compile(
    rf'(\[\[package\]\]\nname = "{re.escape(PROJECT_NAME)}"\nversion = ")(?P<version>\d+\.\d+\.\d+)(")',
    re.MULTILINE,
)


class ReleaseError(Exception):
    """Raised for release workflow errors."""


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or "unknown git error"
        raise ReleaseError(f"git {' '.join(args)} failed: {details}")
    return result.stdout.strip()


def ensure_clean_worktree() -> None:
    status = run_git("status", "--porcelain")
    if status:
        raise ReleaseError(
            "Working tree is not clean. Commit/stash changes before running release script."
        )


def parse_current_version(pyproject_content: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.search(pyproject_content)
    if not match:
        raise ReleaseError("Could not find [project].version in pyproject.toml")

    try:
        major, minor, patch = map(int, match.group("version").split("."))
    except ValueError as error:
        raise ReleaseError(
            "Version in pyproject.toml is not valid semver (X.Y.Z)"
        ) from error

    return major, minor, patch


def bump_version(version: tuple[int, int, int], part: BumpPart) -> tuple[int, int, int]:
    major, minor, patch = version
    if part == "major":
        return major + 1, 0, 0
    if part == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def format_version(version: tuple[int, int, int]) -> str:
    return ".".join(str(x) for x in version)


def prompt_bump_part() -> BumpPart:
    while True:
        choice = input("Bump type (major/minor/patch): ").strip().lower()
        if choice in {"major", "minor", "patch"}:
            return cast(BumpPart, choice)
        print("Please enter one of: major, minor, patch")


def prompt_changelog_items() -> list[str]:
    print("Enter changelog bullet points (one per line).")
    print("Submit an empty line when done.")

    items: list[str] = []
    while True:
        line = input("- ").strip()
        if not line:
            break
        if line.startswith("* "):
            items.append(line)
        else:
            items.append(f"* {line}")

    if not items:
        raise ReleaseError("At least one changelog item is required")

    return items


def update_pyproject_version(pyproject_content: str, new_version: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}{new_version}{match.group(3)}"

    updated, count = VERSION_PATTERN.subn(replace, pyproject_content, count=1)
    if count != 1:
        raise ReleaseError("Failed to update version in pyproject.toml")
    return updated


def update_uv_lock_version(uv_lock_content: str, new_version: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}{new_version}{match.group(3)}"

    updated, count = UV_LOCK_VERSION_PATTERN.subn(replace, uv_lock_content, count=1)
    if count != 1:
        raise ReleaseError(
            f'Failed to update version for package "{PROJECT_NAME}" in uv.lock'
        )
    return updated


def build_changelog_entry(new_version: str, changelog_items: list[str]) -> str:
    anchor = new_version.replace(".", "-")
    bullets = "\n".join(changelog_items)
    return (
        f".. _v{anchor}:\n\n"
        f"{new_version}\n"
        f"~~~~~~~~~~~~~~~~~~~\n\n"
        f"{bullets}\n\n"
    )


def prepend_changelog_entry(changelog_content: str, entry: str) -> str:
    lines = changelog_content.splitlines()
    if len(lines) < 2:
        raise ReleaseError("CHANGELOG.rst has unexpected format")

    heading = "\n".join(lines[:2]).rstrip()
    rest = "\n".join(lines[2:]).lstrip("\n")

    updated = f"{heading}\n\n{entry}{rest}"
    if not updated.endswith("\n"):
        updated += "\n"
    return updated


def write_files(new_pyproject: str, new_changelog: str, new_uv_lock: str) -> None:
    PYPROJECT_FILE.write_text(new_pyproject, encoding="utf-8")
    CHANGELOG_FILE.write_text(new_changelog, encoding="utf-8")
    UV_LOCK_FILE.write_text(new_uv_lock, encoding="utf-8")


def create_commit_and_tag(new_version: str) -> None:
    tag_name = f"v{new_version}"
    run_git(
        "add",
        str(PYPROJECT_FILE.name),
        str(CHANGELOG_FILE.name),
        str(UV_LOCK_FILE.name),
    )
    run_git("commit", "-m", f"Release {tag_name}")
    run_git("tag", tag_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bump version, update changelog, commit, and create git tag."
    )
    parser.add_argument(
        "part",
        nargs="?",
        choices=["major", "minor", "patch"],
        help="Version part to bump. If omitted, script asks interactively.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt and proceed immediately.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        ensure_clean_worktree()

        pyproject_content = PYPROJECT_FILE.read_text(encoding="utf-8")
        changelog_content = CHANGELOG_FILE.read_text(encoding="utf-8")
        uv_lock_content = UV_LOCK_FILE.read_text(encoding="utf-8")

        current_version = parse_current_version(pyproject_content)
        part_value = args.part if args.part else prompt_bump_part()
        part: BumpPart = cast(BumpPart, part_value)
        new_version = format_version(bump_version(current_version, part))

        print(f"Current version: {format_version(current_version)}")
        print(f"New version:     {new_version}")

        changelog_items = prompt_changelog_items()

        if not args.yes:
            confirm = (
                input("Proceed with file updates, commit, and tag? [y/N]: ")
                .strip()
                .lower()
            )
            if confirm != "y":
                print("Cancelled.")
                return 1

        new_pyproject = update_pyproject_version(pyproject_content, new_version)
        new_uv_lock = update_uv_lock_version(uv_lock_content, new_version)
        changelog_entry = build_changelog_entry(new_version, changelog_items)
        new_changelog = prepend_changelog_entry(changelog_content, changelog_entry)

        write_files(new_pyproject, new_changelog, new_uv_lock)
        create_commit_and_tag(new_version)

        print()
        print("Release created successfully.")
        print(f"Created commit: Release v{new_version}")
        print(f"Created tag:    v{new_version}")
        print("Next: push with `git push && git push --tags`")
        return 0

    except ReleaseError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
