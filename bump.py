import argparse
import json
import re
import sys
from pathlib import Path

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
SHORT_VERSION_RE = re.compile(r"^\d+\.\d+$")
BUMP_PART_ALIASES = {
    "major": "major",
    "minor": "minor",
    "patch": "patch",
    "path": "patch",  # common typo alias
}


def normalize_version(version_string: str) -> str:
    version = (version_string or "").strip()
    if SHORT_VERSION_RE.fullmatch(version):
        return f"{version}.0"
    return version


def validate_version(version_string: str) -> str:
    normalized = normalize_version(version_string)
    if not VERSION_RE.fullmatch(normalized):
        raise ValueError(
            f"Invalid version '{version_string}'. Expected format: major.minor.patch"
        )
    return normalized


def sync_version(version_string: str, addon_root: Path) -> None:
    version = validate_version(version_string)
    if not addon_root.is_dir():
        raise FileNotFoundError(f"Addon directory not found: {addon_root}")

    manifest_path = addon_root / "manifest.json"
    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    manifest["version"] = version
    manifest["human_version"] = version
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    version_path = addon_root / "VERSION"
    version_path.write_text(f"{version}\n", encoding="utf-8")

def normalize_bump_part(part: str) -> str:
    normalized = (part or "").strip().lower()
    mapped = BUMP_PART_ALIASES.get(normalized)
    if not mapped:
        valid = ", ".join(sorted(k for k in BUMP_PART_ALIASES if k != "path"))
        raise ValueError(f"Invalid bump part '{part}'. Expected one of: {valid}")
    return mapped

def increment_version(version_string: str, bump_part: str = "patch") -> str:
    version = validate_version(version_string)
    try:
        major, minor, patch = map(int, version.split("."))
    except ValueError as e:
        raise ValueError(
            f"Invalid version '{version_string}'. Expected major.minor.patch"
        ) from e

    part = normalize_bump_part(bump_part)
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1

    return f"{major}.{minor}.{patch}"

def increment_patch(version_string: str) -> str:
    return increment_version(version_string, "patch")

def read_current_version(addon_dir: Path) -> str:
    version_file = addon_dir / "VERSION"
    if version_file.exists():
        version = version_file.read_text(encoding="utf-8").strip()
        return validate_version(version)

    manifest_file = addon_dir / "manifest.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        for key in ("human_version", "version"):
            value = str(manifest.get(key, "")).strip()
            if value:
                try:
                    return validate_version(value)
                except ValueError:
                    continue

    raise FileNotFoundError(
        f"Could not determine current version from {version_file} or {manifest_file}"
    )

def bump_version(addon_dir: Path = Path("addon"), bump_part: str = "patch") -> int:
    try:
        part = normalize_bump_part(bump_part)
        current_version = read_current_version(addon_dir)
        new_version = increment_version(current_version, part)
        print(f"Bumping {part} version: {current_version} → {new_version}")
        sync_version(new_version, addon_dir)
        print(f"Successfully updated manifest.json and VERSION to {new_version}")
        return 0
    except Exception as e:
        print(f"Failed to bump version: {e}")
        return 1

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bump add-on version (major, minor, patch). Default is patch."
    )
    parser.add_argument(
        "part",
        nargs="?",
        default="patch",
        help="Bump part: major, minor, patch (or 'path' alias).",
    )
    parser.add_argument(
        "--addon-dir",
        default="addon",
        help="Path to the addon directory (default: addon).",
    )
    return parser.parse_args(argv[1:])

def main(argv: list[str]) -> int:
    args = parse_args(argv)
    return bump_version(Path(args.addon_dir), args.part)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
