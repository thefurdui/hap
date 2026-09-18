"""Synchronize standalone release files from VERSION and validate release tags."""
import argparse
from datetime import date
import hashlib
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PAYLOADS = ("bin/hap", "templates/hap.kdl")
STABLE_VERSION = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"


def read_version(root):
    contents = (root / "VERSION").read_text()
    if not re.fullmatch(STABLE_VERSION + r"\n?", contents):
        raise ValueError("VERSION must contain a stable MAJOR.MINOR.PATCH without a v prefix or leading zeroes")
    return contents.rstrip("\n")


def release_files(root, version):
    """Validate every input before preparing any filesystem changes."""
    headings = re.findall(r"^## \[([^\]]+)\] - (\S+)$", (root / "CHANGELOG.md").read_text(), re.M)
    if not headings or headings[0][0] != version:
        raise ValueError("The newest dated CHANGELOG.md entry must match VERSION")
    if sum(entry[0] == version for entry in headings) != 1:
        raise ValueError("CHANGELOG.md must have exactly one entry for VERSION")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", headings[0][1]):
        raise ValueError("The release date must use YYYY-MM-DD")
    try:
        date.fromisoformat(headings[0][1])
    except ValueError as error:
        raise ValueError("The release date must be a valid ISO date") from error

    replacements = (
        ("bin/hap", r'^VERSION="[^"\n]*"$', f'VERSION="{version}"'),
        ("install.sh", r'^REF="\$\{HAP_INSTALL_REF:-[^}\n]*\}"$', f'REF="${{HAP_INSTALL_REF:-v{version}}}"'),
        ("README.md", r'^git checkout v\S+$', f"git checkout v{version}"),
    )
    prepared = {}
    for path, pattern, replacement in replacements:
        updated, count = re.subn(pattern, lambda _: replacement, (root / path).read_text(), flags=re.M)
        if count != 1:
            raise ValueError(f"Expected exactly one release version marker in {path}")
        prepared[path] = updated.encode()
    prepared["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(prepared[path] if path in prepared else (root / path).read_bytes()).hexdigest()}  {path}\n"
        for path in PAYLOADS
    ).encode()
    return prepared


def check_tag(root, version, tag):
    if tag != f"v{version}":
        raise ValueError(f"Release tag must be v{version}, got {tag}")

    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
        if result.returncode:
            raise ValueError(f"Cannot inspect release tag {tag}: {result.stderr.strip()}")
        return result.stdout.strip()

    ref = f"refs/tags/{tag}"
    if git("cat-file", "-t", ref) != "tag":
        raise ValueError(f"{tag} must be an annotated tag")
    if git("rev-parse", "--verify", ref + "^{commit}") != git("rev-parse", "HEAD"):
        raise ValueError(f"{tag} must point to the checked-out release commit")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Release tag verification requires a clean working tree")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="synchronize release versions and regenerate SHA256SUMS")
    mode.add_argument("--tag", help="also verify this annotated tag matches VERSION and HEAD")
    args = parser.parse_args()
    try:
        version = read_version(ROOT)
        prepared = release_files(ROOT, version)
        stale = [path for path, contents in prepared.items()
                 if not (ROOT / path).is_file() or (ROOT / path).read_bytes() != contents]
        if args.write:
            for path in stale:
                (ROOT / path).write_bytes(prepared[path])
        elif stale:
            raise ValueError(f"Release files differ from VERSION: {', '.join(stale)}; run make release-prepare")
        if args.tag:
            check_tag(ROOT, version, args.tag)
    except (OSError, ValueError) as error:
        sys.exit(str(error))
    print(f"Release v{version}: version, notes, and checksums agree" + ("; annotated tag verified" if args.tag else ""))


if __name__ == "__main__":
    main()
