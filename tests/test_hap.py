"""Integration regressions: all state and Git operations stay in temporary fixtures."""
import os
import hashlib
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

    def test_cleanup_preserves_unique_branch_history(self):
        source, work = self.workspace()
        (work / "file.txt").write_text("unique work")
        self.git(work, "commit", "-qam", "unique")
        tip = self.git(work, "rev-parse", "HEAD").stdout.strip()
        self.hap("clean", "project", "task")
        self.assertFalse(work.exists())
        self.assertEqual(self.git(source, "rev-parse", "hap/task").stdout.strip(), tip)

    def test_cleanup_preserves_detached_history(self):
        source, work = self.workspace()
        self.git(work, "checkout", "--detach", "-q")
        (work / "file.txt").write_text("detached work")
        self.git(work, "commit", "-qam", "detached")
        tip = self.git(work, "rev-parse", "HEAD").stdout.strip()
        self.hap("clean", "project", "task")
        refs = self.git(source, "for-each-ref", "--format=%(objectname)", "refs/hap/recovery").stdout
        self.assertIn(tip, refs)

    def test_remote_delete_preserves_uncommitted_work(self):
        source, work = self.workspace()
        self.git(work, "push", "-qu", "origin", "hap/task")
        (work / "file.txt").write_text("uncommitted")
        self.hap("clean", "project", "task", "-D", "-y", check=False)
        self.assertEqual((work / "file.txt").read_text(), "uncommitted")
        self.assertIn("hap/task", self.git(source, "ls-remote", "--heads", "origin").stdout)

    def test_cleanup_preserves_ignored_and_loose_files(self):
        _, work = self.workspace()
        (work / "ignored.txt").write_text("ignored data")
        self.hap("clean", "project", "task", check=False)
        self.assertTrue(work.exists())
        (work / "ignored.txt").unlink()
        (work.parent / ".notes").write_text("workspace notes")
        self.hap("clean", "project", "task", check=False)
        self.assertTrue((work.parent / ".notes").exists())

    def test_cleanup_respects_git_lock(self):
        source, work = self.workspace()
        self.git(source, "worktree", "lock", work)
        self.hap("clean", "project", "task", check=False)
        self.assertTrue(work.exists())

    def test_cleanup_stops_on_inspection_failure(self):
        _, work = self.workspace()
        self.stub("git", f'if [ "$3" = status ]; then exit 128; fi\nexec "{GIT}" "$@"')
        self.hap("clean", "project", "task", check=False)
        self.assertTrue(work.exists())

    def test_bulk_cleanup_uses_registered_session_alias(self):
        _, work = self.workspace()
        self.register("alias")
        self.env["HAP_TEST_SESSIONS"] = "alias-task"
        self.hap("clean", "alias")
        self.assertTrue(work.exists())

    def test_bulk_cleanup_preserves_unknown_session_activity(self):
        _, work = self.workspace()
        self.env["HAP_TEST_SESSION_EXIT"] = "1"
        self.assertNotEqual(self.hap("clean", "project", check=False).returncode, 0)
        self.assertTrue(work.exists())

    def test_targeted_cleanup_preserves_main_and_active_workspaces(self):
        _, work = self.workspace("main")
        self.assertNotEqual(self.hap("clean", "project", "main", check=False).returncode, 0)
        self.assertTrue(work.exists())
        work.parent.rename(work.parent.with_name("task"))
        self.env["HAP_TEST_SESSIONS"] = "project-task"
        self.assertNotEqual(self.hap("clean", "project", "task", check=False).returncode, 0)

    def test_targeted_cleanup_preserves_protected_branch(self):
        _, work = self.workspace()
        self.git(work, "switch", "-c", "main")
        self.assertNotEqual(self.hap("clean", "project", "task", check=False).returncode, 0)
        self.assertTrue(work.exists())

    def test_init_preserves_tracked_config_directory(self):
        self.repo(self.project, {"config/app.txt": "application config", "file.txt": "original"})
        self.hap("init", "app")
        self.assertEqual((self.project / "sources/app/config/app.txt").read_text(), "application config")
        self.assertEqual((self.project / "workspaces/main/app/config/app.txt").read_text(), "application config")

    def test_init_rejects_unborn_repository_before_moves(self):
        self.git(self.project, "init", "-q", "-b", "dev")
        self.assertNotEqual(self.hap("init", "app", check=False).returncode, 0)
        self.assertTrue((self.project / ".git").exists())
        self.assertFalse((self.project / "sources").exists())

    def test_init_rolls_back_failed_worktree_creation(self):
        self.repo(self.project)
        (self.project / ".env").write_text("local config")
        self.stub("git", f'if [ "$3" = worktree ] && [ "$4" = add ]; then exit 42; fi\nexec "{GIT}" "$@"')
        self.assertNotEqual(self.hap("init", "app", check=False).returncode, 0)
        self.assertTrue((self.project / ".git").is_dir())
        self.assertEqual((self.project / ".env").read_text(), "local config")
        self.assertFalse((self.project / ".hap-init-journal").exists())
        self.assertFalse((self.project / "sources").exists())
        self.assertEqual(self.git(self.project, "branch", "--show-current").stdout.strip(), "dev")

    def test_init_refuses_local_work_before_migration(self):
        self.repo(self.project)
        (self.project / "file.txt").write_text("my edits")
        self.assertNotEqual(self.hap("init", "app", check=False).returncode, 0)
        self.assertEqual((self.project / "file.txt").read_text(), "my edits")
        self.assertTrue((self.project / ".git").exists())
        self.git(self.project, "restore", "file.txt")
        (self.project / "notes.txt").write_text("untracked")
        self.assertNotEqual(self.hap("init", "app", check=False).returncode, 0)
        (self.project / "notes.txt").unlink()
        (self.project / "ignored.txt").write_text("ignored work")
        self.assertNotEqual(self.hap("init", "app", check=False).returncode, 0)
        self.assertFalse((self.project / "sources").exists())

    def test_init_requires_stopped_state_and_keeps_sqlite_companions(self):
        self.repo(self.project, {"file.txt": "x", ".gitignore": "*.sqlite*\n"})
        names = ["dev.sqlite", "dev.sqlite-wal", "dev.sqlite-shm", "dev.sqlite-journal"]
        for name in names:
            (self.project / name).write_text(name)
        self.assertNotEqual(self.hap("init", "app", check=False).returncode, 0)
        self.assertTrue((self.project / ".git").exists())
        self.hap("init", "app", "--state-stopped")
        for name in names:
            self.assertEqual((self.project / "data/app" / name).read_text(), name)

    def test_init_keeps_tracked_state_examples_in_git(self):
        self.repo(self.project, {".env.example": "example", "fixture.sqlite": "fixture"})
        self.hap("init", "app")
        self.assertEqual((self.project / "sources/app/.env.example").read_text(), "example")
        self.assertFalse((self.project / "shared/app/.env.example").exists())
        self.assertFalse((self.project / "data/app/fixture.sqlite").exists())

    def test_generated_state_is_not_staged(self):
        self.repo(files={"file.txt": "x"})
        shared = self.project / "shared/app"
        shared.mkdir(parents=True)
        (shared / ".env").write_text("config")
        self.register()
        self.hap("open", "project", "task")
        work = self.project / "workspaces/task/app"
        self.git(work, "add", ".")
        self.assertEqual(self.git(work, "ls-files", ".env").stdout, "")

    def test_init_preserves_existing_external_worktrees(self):
        self.repo(self.project)
        external = self.base / "external"
        self.git(self.project, "worktree", "add", "-q", "-b", "other", external)
        self.assertNotEqual(self.hap("init", "app", check=False).returncode, 0)
        self.git(external, "status", "--porcelain")
        self.assertTrue((self.project / ".git").is_dir())

    def test_init_provisions_main_config(self):
        self.repo(self.project)
        (self.project / ".env").write_text("local configuration")
        self.hap("init", "app")
        self.assertEqual((self.project / "workspaces/main/app/.env").read_text(), "local configuration")

    def test_init_reports_every_extracted_file(self):
        self.repo(self.project, {"file.txt": "x", ".gitignore": ".env*\n*.db\n"})
        for name in (".env", ".env.local", "dev.db"):
            (self.project / name).write_text("state")
        result = self.hap("init", "app", "--state-stopped")
        self.assertIn("Config: .env ->", result.stdout)
        self.assertIn("Config: .env.local ->", result.stdout)
        self.assertIn("Data: dev.db ->", result.stdout)

    def test_workspace_retry_repairs_partial_creation(self):
        self.repo(self.project / "sources/a")
        other = self.repo(self.project / "sources/b")
        self.git(other, "branch", "-m", "main")
        self.git(other, "update-ref", "-d", "refs/remotes/origin/dev")
        self.register()
        self.assertNotEqual(self.hap("open", "project", "task", "-b", "dev", check=False).returncode, 0)
        work = self.project / "workspaces/task"
        self.assertFalse((work / ".hap-ready").exists())
        self.git(other, "branch", "dev", "main")
        self.hap("open", "project", "task")
        self.assertTrue((work / "a/.git").exists())
        self.assertTrue((work / "b/.git").exists())
        self.assertTrue((work / ".hap-ready").exists())
        self.assertFalse((self.project / ".hap-lock").exists())

    def test_project_lock_blocks_parallel_mutation(self):
        self.repo()
        self.register()
        (self.project / ".hap-lock").mkdir()
        self.assertNotEqual(self.hap("open", "project", "task", check=False).returncode, 0)
        self.assertFalse((self.project / "workspaces/task").exists())

    def test_failed_install_blocks_readiness_and_can_retry(self):
        self.repo(files={"file.txt": "x", "pnpm-lock.yaml": "fixture"})
        self.register()
        self.stub("pnpm", 'sleep 0.1\nprintf finished > "$PWD/install.finished"\nexit 7')
        result = self.hap("open", "project", "task", check=False)
        self.assertNotEqual(result.returncode, 0)
        work = self.project / "workspaces/task"
        self.assertTrue((work / "app/install.finished").exists())
        self.assertFalse((work / ".hap-ready").exists())
        self.assertFalse((self.base / "commands.log").exists())
        self.stub("pnpm", "exit 0")
        self.hap("open", "project", "task")
        self.assertTrue((work / ".hap-ready").exists())

    def test_registry_sole_entry_upsert_and_remove(self):
        self.hap("add", "app", self.project)
        self.hap("add", "app", self.project)
        self.hap("remove", "app")
        db = Path(self.env["XDG_DATA_HOME"]) / "hap/projects.csv"
        self.assertEqual(db.read_text(), "")

    def test_registry_matches_names_literally(self):
        self.hap("add", "axb", self.project)
        self.hap("add", "a.b", self.project)
        self.hap("remove", "a.b")
        db = Path(self.env["XDG_DATA_HOME"]) / "hap/projects.csv"
        self.assertIn("axb|", db.read_text())
        self.assertNotIn("a.b|", db.read_text())

    def test_registry_rejects_delimiter_paths(self):
        bad = self.base / "bad|path"
        bad.mkdir()
        self.assertNotEqual(self.hap("add", "app", bad, check=False).returncode, 0)

    def test_concurrent_registry_updates_preserve_all_entries(self):
        processes = [subprocess.Popen([str(HAP), "add", f"app-{i}", str(self.project)],
                                     cwd=self.project, env=self.env, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for i in range(8)]
        for process in processes:
            out, err = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, out + err)
        db = Path(self.env["XDG_DATA_HOME"]) / "hap/projects.csv"
        self.assertEqual({line.split("|")[0] for line in db.read_text().splitlines()},
                         {f"app-{i}" for i in range(8)})
        self.assertFalse((db.parent / ".registry.lock").exists())

    def test_empty_sources_fail_before_workspace_creation(self):
        (self.project / "sources").mkdir()
        self.register()
        self.assertNotEqual(self.hap("open", "project", "task", check=False).returncode, 0)
        self.assertFalse((self.project / "workspaces").exists())

    def test_linked_worktree_sources_are_rejected(self):
        original = self.repo(self.base / "original")
        source = self.project / "sources/linked"
        source.parent.mkdir()
        self.git(original, "worktree", "add", "-q", "-b", "linked", source)
        self.register()
        self.assertNotEqual(self.hap("open", "project", "task", check=False).returncode, 0)
        self.assertFalse((self.project / "workspaces").exists())

    def test_default_base_uses_repository_branch(self):
        source = self.repo()
        self.git(source, "branch", "-m", "main")
        self.register()
        self.hap("open", "project", "task")
        work = self.project / "workspaces/task/app"
        self.assertEqual(self.git(work, "branch", "--show-current").stdout.strip(), "hap/task")

    def test_existing_branch_requires_explicit_reuse(self):
        source = self.repo()
        self.git(source, "branch", "hap/task")
        self.register()
        self.assertNotEqual(self.hap("open", "project", "task", check=False).returncode, 0)
        self.hap("open", "project", "task", "--reuse-branch")
        self.assertTrue((self.project / "workspaces/task/app/.git").exists())

    def test_editor_failure_is_reported(self):
        self.workspace()
        self.env["HAP_TEST_EDITOR_EXIT"] = "9"
        self.assertNotEqual(self.hap("open", "project", "task", check=False).returncode, 0)
        self.assertFalse((self.project / "workspaces/task/.hap-opening").exists())

    def test_bulk_cleanup_reports_preserved_dirty_workspace(self):
        _, work = self.workspace()
        (work / "file.txt").write_text("dirty")
        self.assertNotEqual(self.hap("clean", "project", check=False).returncode, 0)
        self.assertTrue(work.exists())

    def test_push_failure_is_reported(self):
        self.repo()
        self.register()
        self.stub("git", f'if [ "$3" = push ]; then exit 9; fi\nexec "{GIT}" "$@"')
        self.assertNotEqual(self.hap("open", "project", "task", check=False).returncode, 0)
        self.assertFalse((self.project / "workspaces/task/.hap-ready").exists())

    def installer_fixture(self):
        downloads = self.base / "downloads"
        downloads.mkdir()
        manifest = []
        for relative in ("bin/hap", "templates/hap.kdl"):
            body = (ROOT / relative).read_bytes()
            (downloads / Path(relative).name).write_bytes(body)
            manifest.append(f"{hashlib.sha256(body).hexdigest()}  {relative}\n")
        (downloads / "SHA256SUMS").write_text("".join(manifest))
        self.env.update(HAP_TEST_DOWNLOAD=str(downloads), HAP_BIN_DIR=str(self.base / "installed/bin"),
                        HAP_DATA_DIR=str(self.base / "installed/data"))
        self.stub("curl", 'out=""\nwhile [ "$#" -gt 0 ]; do\n if [ "$1" = --output ]; then out="$2"; shift 2; else url="$1"; shift; fi\ndone\nfile="${url##*/}"\n[ "$file" != "${HAP_TEST_FAIL_DOWNLOAD:-}" ] || exit 22\ncp "$HAP_TEST_DOWNLOAD/$file" "$out"')
        executable = Path(self.env["HAP_BIN_DIR"]) / "hap"
        executable.parent.mkdir(parents=True)
        executable.write_text("old executable")
        return downloads, executable

    def test_installer_preserves_install_on_download_failure(self):
        _, executable = self.installer_fixture()
        self.env["HAP_TEST_FAIL_DOWNLOAD"] = "hap.kdl"
        self.assertNotEqual(self.run_cmd(["bash", ROOT / "install.sh"], check=False).returncode, 0)
        self.assertEqual(executable.read_text(), "old executable")

    def test_installer_verifies_checksums_before_replacement(self):
        downloads, executable = self.installer_fixture()
        (downloads / "hap").write_text("corrupt")
        self.assertNotEqual(self.run_cmd(["bash", ROOT / "install.sh"], check=False).returncode, 0)
        self.assertEqual(executable.read_text(), "old executable")

    def test_installer_installs_verified_pair(self):
        _, executable = self.installer_fixture()
        self.run_cmd(["bash", ROOT / "install.sh"])
        self.assertEqual(executable.read_bytes(), HAP.read_bytes())
        self.assertEqual((Path(self.env["HAP_DATA_DIR"]) / "templates/hap.kdl").read_bytes(),
                         (ROOT / "templates/hap.kdl").read_bytes())

    def test_make_handles_spaces_and_preserves_unowned_files(self):
        prefix = self.base / "install with spaces"
        args = [f"BINDIR={prefix}/bin", f"DATADIR={prefix}/data"]
        self.run_cmd(["make", "install", *args], cwd=ROOT)
        sentinel = prefix / "data/templates/unowned"
        sentinel.write_text("keep")
        self.run_cmd(["make", "uninstall", *args], cwd=ROOT)
        self.assertFalse((prefix / "bin/hap").exists())
        self.assertEqual(sentinel.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
