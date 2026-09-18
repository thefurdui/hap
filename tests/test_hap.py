"""Integration regressions: all state and Git operations stay in temporary fixtures."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HAP = ROOT / "bin/hap"
GIT = shutil.which("git")


class HapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hap-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.stubs = self.base / "bin"
        self.stubs.mkdir()
        self.env = os.environ.copy()
        self.env.update(
            PATH=str(self.stubs) + os.pathsep + self.env["PATH"],
            XDG_DATA_HOME=str(self.base / "xdg"),
            GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_NAME="Hap Test", GIT_AUTHOR_EMAIL="hap@example.invalid",
            GIT_COMMITTER_NAME="Hap Test", GIT_COMMITTER_EMAIL="hap@example.invalid",
            GIT_TERMINAL_PROMPT="0", HAP_TEST_LOG=str(self.base / "commands.log"),
        )
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_CONFIG_COUNT", "ZELLIJ"):
            self.env.pop(key, None)
        self.stub("zellij", 'if [ "$1" = list-sessions ]; then printf "%s\\n" "${HAP_TEST_SESSIONS:-}"; exit "${HAP_TEST_SESSION_EXIT:-0}"; fi\nprintf "%s\\n" "$*" >> "$HAP_TEST_LOG"\nexit "${HAP_TEST_EDITOR_EXIT:-0}"')
        self.stub("cursor", 'exit "${HAP_TEST_EDITOR_EXIT:-0}"')
        self.stub("fzf", "exit 0")

    def stub(self, name, body):
        path = self.stubs / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def run_cmd(self, args, cwd=None, check=True):
        result = subprocess.run(list(map(str, args)), cwd=cwd or self.project,
                                env=self.env, text=True, capture_output=True, timeout=20)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def hap(self, *args, check=True, cwd=None):
        return self.run_cmd([HAP, *args], cwd=cwd, check=check)

    def git(self, repo, *args, check=True):
        return self.run_cmd([GIT, "-C", repo, *args], check=check)

    def repo(self, path=None, files=None):
        path = path or self.project / "sources/app"
        path.mkdir(parents=True, exist_ok=True)
        self.git(path, "init", "-q", "-b", "dev")
        for name, text in (files or {"file.txt": "original\n", ".gitignore": ".env\n*.db\nignored.txt\n"}).items():
            dest = path / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
        self.git(path, "add", ".")
        self.git(path, "commit", "-qm", "initial")
        # A local bare remote prevents fixture commands from using the network.
        remote = self.base / (path.name + "-remote.git")
        if not remote.exists():
            self.run_cmd([GIT, "init", "--bare", "-q", remote])
        self.git(path, "remote", "add", "origin", remote)
        self.git(path, "push", "-qu", "origin", "dev")
        return path

    def register(self, name="project"):
        db = Path(self.env["XDG_DATA_HOME"]) / "hap/projects.csv"
        db.parent.mkdir(parents=True, exist_ok=True)
        db.write_text(f"{name}|{self.project}\n")
        return db

    def workspace(self, name="task"):
        source = self.repo()
        target = self.project / "workspaces" / name / "app"
        target.parent.mkdir(parents=True, exist_ok=True)
        self.git(source, "worktree", "add", "-q", "-b", "hap/" + name, target, "dev")
        self.register()
        return source, target

    def test_reject_workspace_traversal(self):
        self.workspace()
        victim = self.project / "data"
        victim.mkdir()
        (victim / "keep").write_text("valuable")
        result = self.hap("clean", "project", "../data", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((victim / "keep").exists())

    def test_reject_symlink_workspace(self):
        self.workspace()
        outside = self.base / "outside"
        outside.mkdir()
        (self.project / "workspaces/link").symlink_to(outside)
        self.assertNotEqual(self.hap("clean", "project", "link", check=False).returncode, 0)
        self.assertTrue(outside.exists())

    def test_reject_init_and_profile_traversal(self):
        self.repo(self.project)
        self.assertNotEqual(self.hap("init", "../escape", check=False).returncode, 0)
        self.assertTrue((self.project / ".git").exists())
        self.register()
        self.assertNotEqual(self.hap("open", "project", "-p", "../../outside", check=False).returncode, 0)

    def test_shared_link_does_not_follow_branch_symlink(self):
        source = self.repo()
        outside = self.base / "outside"
        outside.mkdir()
        (outside / ".env").write_text("unrelated")
        (source / "config").symlink_to(outside)
        self.git(source, "add", "config")
        self.git(source, "commit", "-qm", "directory symlink")
        shared = self.project / "shared/app/config"
        shared.mkdir(parents=True)
        (shared / ".env").write_text("config")
        self.register()
        self.assertNotEqual(self.hap("open", "project", "task", check=False).returncode, 0)
        self.assertEqual((outside / ".env").read_text(), "unrelated")
        self.assertFalse((outside / ".env").is_symlink())


if __name__ == "__main__":
    unittest.main()
