# Changelog

## [1.2.0] - 2026-09-18

This release addresses all 32 findings from the security and implementation review. Each finding has its own conventional commit; the [implementation record](docs/v1.2.0-work.md) lists the complete scope.

### Changes requiring attention

- Workspace creation is local by default. Dependency commands, remote publication, and fetching require `--install`, `--publish`, and `--fetch` respectively. Dependency installation finishes successfully before launching a session.
- Configuration seeds are copied with private permissions. `--shared-config` explicitly enables writable shared links. Existing local edits survive reopening and prevent cleanup from deleting their workspace.
- Each workspace gets a separate data directory, exposed through `HAP_DATA_DIR`. Applications must use this path; new workspaces do not clone existing databases. `--shared-data` explicitly selects shared data. Upgrading does not move existing databases automatically.
- Cleanup retains local branches and workspace data. Recreating a retained branch requires `--reuse-branch`. Detached commits receive recovery refs before worktree removal.
- Init requires clean, committed repositories without external linked worktrees. Unknown ignored files must be preserved elsewhere first. Database migration requires `--state-stopped` after stopping database users.
- Zellij session names now derive from project and workspace paths, so aliases share one identity. Legacy sessions remain available for manual attachment and continue to protect their workspaces while their aliases are registered.
- Bash 4+ and Git 2.31+ are required. The default layout uses Bash and leaves application/editor commands to project configuration.

See [Upgrading from v1.1](README.md#upgrading-from-v11) for migration steps.

### Security and data preservation

- Validate project, workspace, repository, and profile names and enforce filesystem boundaries. Refuse unsafe symlinks, Git metadata destinations, tracked-file replacement, and destination conflicts.
- Protect main, active or resumable sessions, long-lived branches, dirty worktrees, ignored files, loose workspace files, and locked worktrees. Unknown session or Git inspection results prevent deletion.
- Verify remote tips and use leases for explicit remote branch deletion. Remote deletion flags never bypass checks for local edits. Git removal failures have no recursive-delete fallback.
- Journal initialization, roll back failed moves and provisioning, and support `init --recover` after an interruption. Reject inputs that cannot be completely migrated before moving them.
- Migrate only recognized ignored state. Preserve SQLite WAL, SHM, and rollback sidecars alongside stopped databases and report every extracted file's actual destination.
- Copy config without following destination symlinks, record generated state, and exclude it from accidental Git staging. Preserve unrecognized or edited state during cleanup.
- Validate literal registry records, reject unsafe registry file types, serialize concurrent writers, and replace complete registry files atomically.
- Download a selected release or commit over HTTPS, verify the executable and layout against `SHA256SUMS`, and stage replacements with rollback. The manifest detects corruption; it is not an independent publisher signature.
- Quote Makefile paths and restrict uninstall to owned files. Runtime and installers consistently honor XDG data locations.

### Reliability and maintenance

- Serialize workspace mutation and repair incomplete setup on retry. Validate source repositories, base commits, branch reuse, editors, and required tools before workspace changes.
- Propagate dependency, editor, publication, and cleanup failures through exit status.
- Preserve saved Zellij sessions; wait for GUI editors and provide `hap unlock` for stale markers with live-owner checks.
- Preserve filename boundaries during discovery and propagate traversal failures. Report unsupported state filenames explicitly.
- Add integration regressions, Bash syntax checks, ShellCheck, release consistency checks, and Linux/macOS CI.
- Make `VERSION` authoritative, synchronize standalone release files with `make release-prepare`, and validate annotated release tags against the version and commit in CI.
- Rewrite help, lifecycle documentation, recovery guidance, and the generic layout to match the implemented behavior.
