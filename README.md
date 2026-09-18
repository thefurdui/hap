# hap

A Bash CLI for parallel development with Git worktrees and Zellij or GUI editors. Each workspace gets separate checkouts, copied configuration, and its own data directory. Workspaces are organizational isolation, not a sandbox: their processes still run as your Unix user.

## Requirements and installation

- Bash 4+ and Git 2.31+ for workspace operations. On macOS, put Homebrew Bash ahead of `/bin/bash` on PATH.
- Zellij, Cursor, or Antigravity, depending on the selected editor. GUI integration uses the editor's `--wait` option.
- `fzf` only for the interactive project picker.
- `pnpm` or Go only when explicitly installing dependencies for repositories using them.
- Standard Unix tools including `find`, `awk`, and `mktemp`.

Install from a reviewed checkout:

```sh
git clone https://github.com/thefurdui/hap.git
cd hap
git checkout v1.2.0
make install
```

`make install` defaults to `~/.local/bin/hap` and `${XDG_DATA_HOME:-$HOME/.local/share}/hap/templates/`. Override `PREFIX`, `BINDIR`, or `DATADIR` as needed. Add the executable directory to PATH. `make uninstall` removes only the executable and distributed template; it keeps the project registry and project files.

The release downloader is also available as `bash install.sh` from a reviewed checkout. It defaults to `v1.2.0`, requires HTTPS and successful HTTP responses, verifies `SHA256SUMS`, and stages both files before replacement. Set `HAP_INSTALL_REF` to a released version tag or a full commit SHA; use `HAP_BIN_DIR` and `HAP_DATA_DIR` to override installation destinations. The checksum manifest and installer share the repository's trust boundary; checksums are not an independent signature against a compromised publisher.

## Project structure

```text
project/
├── sources/                      # ordinary Git checkouts, detached after init
│   └── app/
├── workspaces/
│   ├── main/app/                 # linked Git worktree on the original branch
│   └── task/app/                 # linked worktree on hap/task
├── shared/app/                   # ignored configuration seeds
├── data/
│   ├── workspaces/main/app/      # original stopped database and companions
│   ├── workspaces/task/app/      # separate data for this workspace
│   └── shared/app/               # only used with --shared-data
└── config/
    ├── hap.kdl
    └── profiles/                 # optional named layouts
```

The source repositories are **not bare repositories**. Every linked worktree shares its source's Git object store and refs. Local branches remain after cleanup, and detached tips receive recovery refs.

`shared/` holds configuration seeds. New workspaces receive ordinary copies with mode `0600`, so editing one workspace's `.env` does not change another workspace. `--shared-config` explicitly opts into writable shared symlinks. Existing generated state is kept on subsequent opens; opening does not refresh or overwrite local edits. The `.hap-state/` metadata records generated paths and their initial hashes or link targets so cleanup can recognize unchanged files. Generated files are added to Git's local exclusion rules.

Databases live outside worktrees. `HAP_DATA_DIR` is exported into sessions and points to `data/workspaces/<workspace>/`, or `data/shared/` with `--shared-data`. Applications must actually use this path. For example, customize a server command to set:

```sh
DB_PATH="$HAP_DATA_DIR/app/dev.db" ./start-server
```

Hap does not rewrite arbitrary `.env` contents, expand variables inside dotenv files, assign server ports, or clone live databases. New workspaces start with empty data directories. Use your database's supported backup/restore mechanism if they need seed data. Cleanup never deletes their data directories.

## Initialize a project

Run inside a normal Git checkout or a directory containing normal checkouts:

```sh
hap init                     # project name defaults to the directory name
hap init my-project          # choose a registry name
hap init my-project --state-stopped
```

Before initialization:

1. Stop processes using the repositories and databases.
2. Commit or otherwise preserve tracked changes and ordinary untracked files. Back up or remove unknown ignored files, including rebuildable dependency caches, before retrying.
3. Check out an existing branch. Repositories without commits, detached checkouts, linked-worktree inputs, and repositories with existing external worktrees are rejected before migration.
4. If ignored database files exist, pass `--state-stopped` after stopping their users. This is your assertion that migration is safe; hap does not stop services for you.

Init validates the inputs, records a recovery journal, moves each repository into `sources/`, extracts recognized **ignored and untracked** state, and creates `workspaces/main/` on the original branches. Main receives the same configuration setup as later workspaces. Tracked `.env.example` files, certificates, logs, and database fixtures remain tracked application files. Application directories named `config`, `data`, or `shared` inside a root repository move with that repository.

Recognized config patterns are `.env`, `.env.*`, `*.pem`, `*.crt`, and `*.key`. Data patterns include `*.db`, `*.sqlite`, `*.sqlite3`, their `-wal`, `-shm`, and `-journal` companions, and `*.log`. Scanning excludes `.git`, `node_modules`, `vendor`, `dist`, and `build`. Unknown ignored files or state symlinks must be handled explicitly first. Non-repository files in a multi-repository project are left where they are.

On an ordinary failure, hap attempts to reverse recorded moves and restore the original branch attachment. A crash or recovery conflict leaves `.hap-init-journal/` for inspection. After preserving any files changed since the failure, resume recovery with:

```sh
hap init --recover
```

Recovery refuses conflicts rather than overwriting newer work. Do not discard the journal while it contains unresolved operations.

Then edit `config/hap.kdl` and configure database paths using the actual destinations printed by init. Relative path resolution depends on the application consuming the value, not on where an env file happens to live.

SQLite does not generally lose locking simply because a path is a symlink: its Unix interface has attempted canonical symlink resolution since 3.10.0. Moving an open database or separating it from a hot journal is a different, real risk. See [SQLite's corruption guidance](https://www.sqlite.org/howtocorrupt.html). Hap avoids symlinked database provisioning and requires stopped state during migration.

## Open a workspace

```sh
hap                              # interactive project picker
hap open my-project              # initial main workspace
hap open my-project task         # create or validate/resume task
hap open my-project task -b main
hap open my-project task -B feat/login
hap open my-project task --reuse-branch
hap open my-project task --install --publish
hap open my-project task -u
hap open my-project task -e cursor
```

| Option | Behavior |
| --- | --- |
| `-u` | Set `HAP_UP=1` for a new session's server commands. |
| `-e <editor>` | Select `zellij` (default), `cursor`, or `antigravity`. |
| `-b <ref>` | Select the base for new branches. |
| `-B <branch>` | Select the target branch name; default is `hap/<workspace>`. |
| `--reuse-branch` | Deliberately reuse an existing target branch. |
| `--fetch` | Fetch origin before resolving bases. |
| `--install` | Run the repository's pnpm install or Go module download and wait for success. |
| `--publish` | Push each selected workspace branch to origin. |
| `--shared-config` | Use writable shared config links when provisioning new config paths. |
| `--shared-data` | Export the shared data directory instead of workspace-specific data. |
| `-p`, `--profile <name>` | Select `config/profiles/<name>.kdl`. Without a name, list profiles. |

Ordinary `open` does not install dependencies, fetch, or push. Installation can execute repository-controlled code with your permissions, so `--install` is for trusted repositories. Layout files also contain executable commands; use trusted layouts. `-u` only controls server commands that honor `HAP_UP`.

Without `-b`, the base is resolved from the source repository's `hap.baseBranch` Git setting, then cached `origin/HEAD`, then the source's attached branch or detached HEAD. This is a local snapshot unless you request `--fetch`. Set a per-repository policy with:

```sh
git -C sources/app config hap.baseBranch main
```

Initialization failures and dependency failures leave a workspace unready. A later open validates each repository and fills in missing worktrees; it does not assume an existing directory is complete. Existing unrelated directories or conflicting files are preserved and reported.

Project mutations are serialized with `.hap-lock/`. If a process was killed, inspect the lock's owner and the interrupted operation before manually removing a stale lock. Registry updates use a separate lock and atomic file replacement.

## Sessions and layouts

Existing Zellij sessions are attached or resurrected without deleting saved session state. Profiles and `-u` affect a newly created session; they do not replace an existing session's layout or restart its servers. Stop and start servers from their panes.

Session names use `hap-<workspace>-<path-hash>`, derived from the canonical project path and workspace name. All aliases for one project reach the same session, and ambiguous alias/workspace combinations stay separate. Moving a project changes its session identity.

The distributed template uses Bash shells and no hardcoded repository names, editors, agents, or optional Git UI. Customize pane `cwd` and `command` properties for your project. Named profiles live in `config/profiles/`; profile names cannot escape that directory.

GUI commands use `--wait`. Their workspace remains protected while the CLI waits, and the GUI marker is removed when the editor returns or fails to launch. A killed process or older fire-and-forget version can leave a marker. After closing the editor, explicitly clear stale markers with:

```sh
hap unlock my-project task
```

Unlock refuses a marker whose recorded owner is still running. It does not close editors or terminate Zellij sessions. Session detection failures preserve workspaces rather than treating them as inactive.

## Cleanup and history preservation

```sh
hap clean my-project task
hap clean my-project             # consider all inactive non-main workspaces
hap clean my-project task -D     # also delete matching remote branches; prompts
hap clean my-project task -D -y  # same operation without the prompt
```

Cleanup preserves local branches, workspace data, dirty worktrees, unknown files, ignored local files, edited generated config, Git worktree locks, and active/resumable sessions. Unchanged generated config may be removed with its workspace. There is no recursive-delete fallback when Git refuses removal.

`main` is protected even for targeted cleanup. Standard long-lived branches (`main`, `master`, `dev`, `develop`, `trunk`, `stable`, `release`, and `release/*`), the remote default, and configured base branches are protected. Add exact additional branch names with:

```sh
git -C sources/app config --add hap.protectedBranch production
```

Remote deletion never grants permission to discard local changes. Hap first verifies that the remote tip matches retained local history, then uses a lease so a newer remote update cannot be deleted accidentally. A detached worktree's commit is retained under `refs/hap/recovery/` before removal. Inspect those refs using `git for-each-ref refs/hap/recovery`.

Cleanup can report partial progress if a later Git operation fails. Its exit status is nonzero on a failed inspection or removal. Inspect the output before retrying; preserved branches and data remain available.

## Registry and names

```sh
hap add my-project /absolute/or/relative/path
hap remove my-project            # unregister only
hap list
hap help
hap version
```

The registry is `${XDG_DATA_HOME:-$HOME/.local/share}/hap/projects.csv`, with literal `name|absolute-path` records. Project, repository, workspace, and profile names start with an ASCII letter or digit and contain only letters, digits, dots, underscores, and hyphens. Filesystem paths can contain spaces, but registry paths cannot contain pipes or line breaks. Provisioned state paths cannot contain line breaks; tracked application filenames remain Git's responsibility.

## Upgrading from v1.1

- Read the [v1.2.0 release notes](CHANGELOG.md) before relying on the old cleanup or automatic setup behavior.
- Add `--install` and `--publish` where you deliberately want those actions. Use `--reuse-branch` when recreating a removed workspace whose local branch remains.
- Exact old generated config symlinks are converted to local copies on setup by default. New copies preserve the current seed contents; existing local edits are not overwritten.
- Pre-v1.2 Zellij sessions keep their old `<alias>-<workspace>` names. Attach to them manually while finishing that work; new opens use the path-based identity. Cleanup recognizes legacy names for every currently registered alias and preserves those sessions' workspaces.
- Existing databases are not relocated merely by upgrading or opening a project. Stop database users, back up state, and explicitly migrate/configure application paths for `data/workspaces/<workspace>/<repo>/`. Old hardcoded `.env` paths continue to mean what the application makes them mean.
- Old `.hap.gui` markers can be cleared using `hap unlock` after closing their editors.
- The new template is installed into the template store. Existing `config/hap.kdl` files are not replaced during an upgrade.

## Development

`make check` runs Bash syntax checks, ShellCheck, release consistency checks, and Python unittest integration tests. Tests use temporary projects, local bare remotes, and stubbed editors/installers; they do not operate on your real workspaces or publish to external remotes. CI runs the same checks on Linux and macOS.

After changing `bin/hap` or `templates/hap.kdl`, run `make checksums` and commit `SHA256SUMS` with the change. Release checks require the executable version, installer's default tag, changelog entry, and downloadable file hashes to agree.

The [implementation record](docs/v1.2.0-work.md) maps all 32 review findings to the changes. Python and ShellCheck are development dependencies, not runtime dependencies of hap.

MIT license.
