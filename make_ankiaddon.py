import os
import argparse
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from bump import (
    bump_version as bump_patch_version,
    read_current_version,
    sync_version,
    validate_version,
)

# Configuration
ADDON_NAME = "Auto_Sync"
ADDON_DIR = "addon"

def artifact_names(
    addon_name: str,
    version: str,
    when: datetime | None = None,
) -> tuple[str, str]:
    dt = when or datetime.today()
    timestamp = dt.strftime("%Y%m%d%H%M")
    base = f"{addon_name}_v{version}_{timestamp}"
    return f"{base}.zip", f"{base}.ankiaddon"

def bump_version(addon_path: Path | None = None) -> int:
    target = addon_path or Path(ADDON_DIR)
    return bump_patch_version(target)

def resolve_build_version(
    addon_path: Path,
    explicit_version: str | None = None,
) -> str:
    if explicit_version is None:
        code = bump_version(addon_path)
        if code != 0:
            raise RuntimeError("Failed to bump version.")
        return read_current_version(addon_path)

    version = validate_version(explicit_version)
    sync_version(version, addon_path)
    print(f"Using explicit version: {version}")
    return version

def create_ankiaddon(explicit_version: str | None = None) -> int:
    # Get the project root and addon directory
    root_dir = Path(__file__).resolve().parent
    addon_path = root_dir / ADDON_DIR

    if not addon_path.exists():
        print(f"Error: {ADDON_DIR} directory not found.")
        return 1

    try:
        build_version = resolve_build_version(addon_path, explicit_version)
    except Exception as e:
        print(f"Error: Could not prepare build version: {e}")
        return 1

    zip_name, final_name = artifact_names(ADDON_NAME, build_version)
    zip_path = root_dir / zip_name
    final_path = root_dir / final_name

    # Exclusions
    exclude_dirs = ['__pycache__', '.git', '.vscode', '.github', 'tests']
    exclude_exts = ['.ankiaddon', '.pyc']
    exclude_files = ['meta.json', '.gitignore', '.gitmodules', 'mypy.ini']

    print(f"Creating {final_name} from {ADDON_DIR}...")

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Walk through the addon directory specifically
        for root, dirs, files in os.walk(addon_path):
            # Filter directories in-place
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                file_path = Path(root) / file
                # Skip excluded files/extensions
                if file in exclude_files or file_path.suffix in exclude_exts:
                    continue
                
                # Calculate the path relative to the 'addon/' folder 
                # so that __init__.py is at the root of the zip
                archive_name = file_path.relative_to(addon_path)
                zipf.write(file_path, archive_name)

    # Rename to .ankiaddon
    if final_path.exists():
        final_path.unlink()
    zip_path.replace(final_path)
    print(f"Successfully created: {final_path.name}")
    return 0

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create .ankiaddon package. "
            "If no version is provided, patch version is auto-bumped via bump.py."
        )
    )
    parser.add_argument(
        "version",
        nargs="?",
        help="Optional explicit version (major.minor.patch) to set before packaging.",
    )
    return parser.parse_args(argv[1:])

def main(argv: list[str]) -> int:
    args = parse_args(argv)
    return create_ankiaddon(args.version)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
