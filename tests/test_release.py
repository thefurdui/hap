"""Release synchronization and tag validation in disposable repositories."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hap-release-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = os.environ.copy()
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_CONFIG_COUNT"):
            self.env.pop(key, None)
        self.env.update(
            GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_NAME="Hap Test", GIT_AUTHOR_EMAIL="hap@example.invalid",
            GIT_COMMITTER_NAME="Hap Test", GIT_COMMITTER_EMAIL="hap@example.invalid",
        )
        files = {
            "VERSION": "1.2.0\n",
            "bin/hap": '#!/usr/bin/env bash\nVERSION="1.1.0"\nprintf "hap v%s\\n" "$VERSION"\n',
            "install.sh": 'REF="${HAP_INSTALL_REF:-v1.1.0}"\n',
            "README.md": "git checkout v1.1.0\n",
            "CHANGELOG.md": "# Changelog\n\n## [1.2.0] - 2026-09-18\n\nRelease notes.\n",
            "templates/hap.kdl": "layout { pane }\n",
        }
        for path, text in files.items():
            self.write(path, text)
        (self.root / "bin/hap").chmod(0o755)
        (self.root / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/release_checks.py", self.root / "scripts/release_checks.py")

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def command(self, *args, check=True):
        result = subprocess.run(args, cwd=self.root, env=self.env, capture_output=True,
                                text=True, timeout=20)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def release(self, *args, check=True):
        return self.command(sys.executable, "scripts/release_checks.py", *args, check=check)

    def repository(self):
        self.release("--write")
        self.command("git", "init", "-q", "-b", "main")
        self.command("git", "add", ".")
        self.command("git", "commit", "-qm", "chore(release): v1.2.0")

    def test_version_drives_standalone_files_and_checksums(self):
        self.write("VERSION", "1.3.0\n")
        self.write("CHANGELOG.md", "## [1.3.0] - 2026-10-01\n\n## [1.2.0] - 2026-09-18\n")
        self.release("--write")
        self.release()
        self.assertIn(':-v1.3.0}', (self.root / "install.sh").read_text())
        self.assertEqual((self.root / "README.md").read_text(), "git checkout v1.3.0\n")
        for entry in (self.root / "SHA256SUMS").read_text().splitlines():
            digest, path = entry.split("  ")
            self.assertEqual(digest, hashlib.sha256((self.root / path).read_bytes()).hexdigest())
        (self.root / "VERSION").unlink()
        self.assertEqual(self.command(str(self.root / "bin/hap"), "version").stdout.strip(), "hap v1.3.0")

    def test_check_detects_drift_without_rewriting_files(self):
        self.release("--write")
        for path in ("bin/hap", "install.sh", "README.md", "templates/hap.kdl", "SHA256SUMS"):
            with self.subTest(path=path):
                target = self.root / path
                original = target.read_bytes()
                if path == "templates/hap.kdl":
                    altered = original + b"// changed payload\n"
                elif path == "SHA256SUMS":
                    altered = b"invalid checksum\n"
                else:
                    altered = original.replace(b"1.2.0", b"1.1.0")
                target.write_bytes(altered)
                self.assertNotEqual(self.release(check=False).returncode, 0)
                self.assertEqual(target.read_bytes(), altered)
                target.write_bytes(original)

    def test_invalid_versions_fail_before_writes(self):
        before = (self.root / "bin/hap").read_bytes()
        for version in ("v1.2.0", "01.2.0", "1.02.0", "1.2.00", "1.2", "1.2.0-rc.1", "1.2.0+build", " 1.2.0", "1.2.0\nextra"):
            with self.subTest(version=version):
                self.write("VERSION", version + "\n")
                self.assertNotEqual(self.release("--write", check=False).returncode, 0)
                self.assertEqual((self.root / "bin/hap").read_bytes(), before)
                self.assertFalse((self.root / "SHA256SUMS").exists())

    def test_release_notes_must_be_current_unique_and_dated(self):
        before = (self.root / "bin/hap").read_bytes()
        for notes in ("## [1.1.0] - 2026-09-18\n", "## [1.2.0] - 2026-02-30\n",
                      "## [1.2.0] - 20260918\n", "## [1.2.0] - 2026-09-18\n" * 2):
            with self.subTest(notes=notes):
                self.write("CHANGELOG.md", notes)
                self.assertNotEqual(self.release("--write", check=False).returncode, 0)
                self.assertEqual((self.root / "bin/hap").read_bytes(), before)

    def test_annotated_tag_matches_version_and_head(self):
        self.repository()
        self.command("git", "tag", "-a", "v1.2.0", "-m", "hap v1.2.0")
        self.release("--tag", "v1.2.0")
        self.assertNotEqual(self.release("--tag", "v1.3.0", check=False).returncode, 0)

    def test_missing_or_lightweight_tag_is_rejected(self):
        self.repository()
        self.assertNotEqual(self.release("--tag", "v1.2.0", check=False).returncode, 0)
        self.command("git", "tag", "v1.2.0")
        self.assertNotEqual(self.release("--tag", "v1.2.0", check=False).returncode, 0)

    def test_tag_on_another_commit_is_rejected(self):
        self.repository()
        self.command("git", "tag", "-a", "v1.2.0", "-m", "hap v1.2.0")
        self.command("git", "commit", "--allow-empty", "-qm", "another commit")
        self.assertNotEqual(self.release("--tag", "v1.2.0", check=False).returncode, 0)

    def test_tag_verification_rejects_dirty_worktree(self):
        self.repository()
        self.command("git", "tag", "-a", "v1.2.0", "-m", "hap v1.2.0")
        self.write("uncommitted.txt", "local work\n")
        self.assertNotEqual(self.release("--tag", "v1.2.0", check=False).returncode, 0)
        self.assertEqual((self.root / "uncommitted.txt").read_text(), "local work\n")
