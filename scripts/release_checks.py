"""Keep the downloadable files, installer default, and release notes consistent."""
import argparse
import hashlib
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
PAYLOADS = ("bin/hap", "templates/hap.kdl")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="regenerate SHA256SUMS")
    args = parser.parse_args()

    match = re.search(r'^VERSION="(\d+\.\d+\.\d+)"$', (ROOT / "bin/hap").read_text(), re.M)
    if not match:
        sys.exit("bin/hap must declare a release VERSION")
    version = match.group(1)
    if f'REF="${{HAP_INSTALL_REF:-v{version}}}"' not in (ROOT / "install.sh").read_text():
        sys.exit("install.sh must default to the executable's release version")
    if not re.search(rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$",
                     (ROOT / "CHANGELOG.md").read_text(), re.M):
        sys.exit("CHANGELOG.md must have a dated entry for this release")

    expected = "".join(f"{hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}  {path}\n"
                       for path in PAYLOADS)
    manifest = ROOT / "SHA256SUMS"
    if args.write:
        manifest.write_text(expected)
    elif not manifest.is_file() or manifest.read_text() != expected:
        sys.exit("SHA256SUMS is missing or stale; run make checksums")
    print(f"Release v{version}: version, notes, and checksums agree")


if __name__ == "__main__":
    main()
