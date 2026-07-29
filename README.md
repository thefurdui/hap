# hap

CLI tool for running AI agents in parallel on different git branches. Manages git worktrees, zellij sessions, and server lifecycle across multiple workspaces.

## The Problem

You're working on a feature. An agent is running on it. It takes 20 minutes. You're sitting there. That's 20 minutes gone.

`hap` lets you spin up isolated workspaces — each with its own branch, its own agent, its own terminal session — so you can work on three things at once while agents do the heavy lifting.

## The 4-Pillar Architecture

Every `hap` project is organized into four pillars. Each pillar has one job, and the separation prevents entire categories of bugs (corrupted databases, missing configs, stale locks).

```
your-project/                       ← project root
├── sources/                        ← PILLAR 1: bare truth
│   ├── frontend/                   ← detached HEAD, worktree origin
│   └── backend/
├── workspaces/                     ← PILLAR 2: isolated work
│   ├── main/
│   │   ├── frontend/               ← git worktree
│   │   └── backend/
│   ├── alpha/
│   └── PROJ-1234/
├── shared/                         ← PILLAR 3: static config (symlinked)
│   ├── frontend/
│   │   └── .env
│   └── backend/
│       ├── .env
│       └── certs/
│           └── server.pem
├── data/                           ← PILLAR 4: mutating state (never symlinked)
│   └── backend/
│       └── dev.db
└── config/
    ├── hap.kdl                 ← default layout
    └── profiles/               ← optional named layouts (-p)
        └── auth-beat.kdl
```

| Pillar        | Purpose                                                                                   | Symlinked? | Contents                                                         |
| ------------- | ----------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------- |
| `sources/`    | Bare repos with detached HEAD. The single source of truth for git operations.             | —          | `.git`, all tracked files                                        |
| `workspaces/` | Isolated working copies. Each one gets its own branch, its own agent, its own terminal.   | —          | Git worktrees                                                    |
| `shared/`     | Static, read-only configuration. Automatically symlinked into every workspace.            | ✅ Yes     | `.env`, `.env.*`, `*.pem`, `*.crt`, `*.key`                      |
| `data/`       | Mutating, lock-sensitive state. **Never symlinked.** Accessed via path routing in `.env`. | ❌ Never   | `*.db`, `*.sqlite`, `*.sqlite3`, `*.db-wal`, `*.db-shm`, `*.log` |

### Why `shared/` exists

Config files like `.env` aren't committed to git, but every workspace needs them. `hap` symlinks files from `shared/<repo>/` into each workspace, so you maintain one copy and every branch sees it.

### Why `data/` exists (and why databases are never symlinked)

SQLite uses file-level locking and WAL (Write-Ahead Logging). Symlinks break both mechanisms:

- **WAL corruption:** SQLite creates `*.db-wal` and `*.db-shm` files next to the database. If the database is a symlink, the WAL files end up in the workspace directory, not next to the real database. This silently corrupts data.
- **Lock contention:** Multiple workspaces symlinking to the same database would bypass SQLite's locking, causing concurrent write corruption.

By keeping databases in `data/` and routing to them via `.env` paths, each workspace reads from the same data without symlink hazards.

### Monorepo path preservation

For monorepos, `hap` preserves the internal directory structure when extracting state files. A monorepo like this:

```
my-saas/
├── apps/
│   ├── web/
│   │   └── .env          ← config
│   └── api/
│       ├── .env          ← config
│       └── prisma/
│           └── dev.db    ← database
└── packages/
    └── auth/
        └── auth.pem      ← certificate
```

After `hap init`, the structure is mirrored:

```
my-saas/
├── shared/my-saas/
│   ├── apps/
│   │   ├── web/.env
│   │   └── api/.env
│   └── packages/
│       └── auth/auth.pem
├── data/my-saas/
│   └── apps/
│       └── api/
│           └── prisma/dev.db
└── sources/my-saas/
    └── (everything else)
```

### Configuring `.env` paths for `data/`

After init, you need to update `.env` files in `shared/` to reference their databases in `data/` using relative paths. The path must resolve from the file's eventual location inside a workspace (since it's symlinked there).

**Path math:** from `workspaces/<ws>/<repo>/apps/api/.env`, you need to escape up to the project root — that's 5 levels (`../../../../../`) — then descend into `data/<repo>/apps/api/dev.db`.

```bash
# In shared/my-saas/apps/api/.env:
DB_PATH=../../../../../data/my-saas/apps/api/prisma/dev.db
```

The depth depends on how deeply nested the `.env` file is within the monorepo. `hap init` prints the exact calculation for each extracted file.

## Two Ways to Use It

### Pets (Permanent Workspaces)

You create a few workspaces and keep them around. Name them by domain, by priority, whatever works for you.

```
workspaces/
├── main/          ← your daily driver, servers running here
├── alpha/         ← user-facing features
├── beta/          ← backend / infra work
└── gamma/         ← experiments, spikes
```

When you finish a feature in `alpha`, you merge the branch, check out a new one, and reuse the workspace. The workspace is yours — you maintain it like you maintain your desk.

**Good for:** solo devs, small teams, startups. You know your workspaces, you know what's in each one.

### Cattle (Ephemeral Workspaces)

One workspace per ticket. `PROJ-1234` gets a workspace, a branch, an agent. When the PR is merged, you clean it up. No attachment.

```
workspaces/
├── main/
├── PROJ-1234/     ← created for the ticket, deleted after merge
├── PROJ-1237/
└── PROJ-1241/
```

`hap` handles the creation and cleanup. You don't think about the workspace — you think about the ticket.

**Good for:** teams, corporations, anyone who works off a backlog. Workspaces are disposable.

Both approaches use the exact same commands. The only difference is whether you run `hap clean` after merging.

## Install

**Requires:** `bash` 4.0+, `zellij`, `fzf`, `git`

**Optional:** `lazygit`

**One-line Install:**

```bash
curl -sL https://raw.githubusercontent.com/thefurdui/hap/refs/heads/main/install.sh | bash
```

**Manual Install:**

```bash
git clone https://github.com/thefurdui/hap.git
cd hap
make install
```

## Quick Start

```bash
cd ~/projects/your-project
hap init
```

That's it. `hap init` detects your repos, scaffolds the 4-pillar directory structure, extracts state files (`.env`, databases, certs) into `shared/` and `data/` preserving their internal paths, creates worktrees, copies the layout template, and registers the project.

Then edit `config/hap.kdl` to set your server start commands, update any `.env` paths (if the extraction report tells you to), and:

```bash
hap open your-project -u
```

## Setup

### `hap init`

Run `hap init` inside your project directory. It handles two scenarios:

**Single repo** (`.git` at root):

```bash
cd ~/projects/myapp    # has .git here
hap init
```

**Multiple repos** (subdirectories with `.git`):

```bash
cd ~/projects/myapp    # has frontend/, backend/ with .git inside each
hap init
```

You can pass a custom project name: `hap init my-custom-name`. Defaults to the directory name.

**What it does:**

1. Scans for git repos (level 0: root `.git`, level 1: subdirs with `.git`)
2. Creates the 4-pillar scaffold: `sources/`, `workspaces/main/`, `shared/`, `data/`, `config/`
3. **Extracts shared state** (`.env`, `.env.*`, `*.pem`, `*.crt`, `*.key`) from each repo into `shared/<repo>/`, preserving internal directory structure
4. **Extracts mutating state** (`*.db`, `*.sqlite`, `*.sqlite3`, `*.db-wal`, `*.db-shm`, `*.log`) into `data/<repo>/`, preserving internal directory structure
5. Moves each repo into `sources/<name>/`
6. Detaches HEAD in each source repo, creates a worktree in `workspaces/main/<name>/` on the original branch
7. Moves any leftover files/dirs into `misc/`
8. Copies `hap.kdl` template into `config/`
9. Registers the project in `~/.local/share/hap/projects.csv`
10. **Prints a state extraction report** showing exactly what was moved and where

Excluded from scanning: `node_modules/`, `vendor/`, `.git/`, `dist/`, `build/`.

**Result (monorepo example):**

```
your-project/
├── config/
│   └── hap.kdl             ← edit this: cwd paths, server commands
├── sources/
│   └── my-saas/            ← detached HEAD, worktree origin
│       └── apps/
│           ├── web/        ← .env extracted to shared/
│           └── api/        ← .env + db extracted
├── workspaces/
│   └── main/
│       └── my-saas/        ← git worktree (your working copy)
│           └── apps/
│               └── api/
│                   └── .env  ← symlink → shared/my-saas/apps/api/.env
├── shared/
│   └── my-saas/
│       └── apps/
│           ├── web/.env
│           └── api/.env
├── data/
│   └── my-saas/
│       └── apps/
│           └── api/
│               └── prisma/dev.db
└── misc/                    ← leftover non-repo files (if any)
```

### Shared State

Files in `shared/` are automatically symlinked into every workspace. `hap init` populates `shared/` for you, but you can also manage it manually:

1. Create a folder in `shared/` named after the repo: `shared/backend/`
2. Mirror the file's relative path: `shared/backend/.env`
3. `hap` will symlink these into every new workspace automatically

### Data State

Files in `data/` are **never symlinked**. Applications access them via paths configured in `.env` files. `hap init` populates `data/` for you during initialization.

To add new databases later, place them directly in `data/<repo>/` and update your `.env` accordingly.

### Manual Registration

If you already have the directory structure set up (or want to register a project without scaffolding):

```bash
hap add your-project /path/to/project
```

## Usage

```
hap <command> [args] [flags]

Commands:
  init [name]                    Scaffold project from current directory
  open <project> [workspace]     Open project or workspace
  add <name> [path]              Register a project
  remove <name>                  Unregister a project
  clean <project> [workspace]    Cleanup workspace(s)
  list                           List registered projects
  help                           Show this help
  version                        Show version

Flags for 'open':
  -u              Auto-start servers (like docker compose up)
  -p, --profile   Layout profile from config/profiles/<name>.kdl
                  (omit name to list: hap open myproject -p)
  -e <editor>     Editor: zellij (default), cursor, antigravity
  -b <branch>     Base branch for new workspace (default: dev)
  -B <branch>     Target branch name (default: hap/<workspace>)

Flags for 'clean':
  -D              Also delete remote branches
  -y              Skip confirmation (with -D)
```

Run `hap` with no arguments for interactive project selection (fzf).

### Open your project (main driver)

```bash
hap                               # interactive picker
hap open myproject                 # direct, servers tab ready but idle
hap open myproject -u              # servers auto-start on session create
hap open myproject -p auth-beat    # use config/profiles/auth-beat.kdl
```

### Open a workspace

```bash
hap open myproject bugfix          # opens "bugfix", creates it if new
hap open myproject bugfix -u       # same, but auto-start servers
hap open myproject bugfix -B feat/login   # custom branch name
hap open myproject bugfix -p landing -u   # profile + workspace
```

What happens when a workspace is created:

1. Creates `workspaces/bugfix/`
2. Adds git worktrees from every repo in `sources/` (branch: `hap/bugfix`)
3. Pushes the branch to origin
4. Installs dependencies in the background (pnpm/go)
5. Symlinks shared state from `shared/` (preserving nested directory structure)
6. Opens a zellij session

If the workspace already exists, it just opens it.

### Servers and the `-u` flag

Every session gets a "servers" tab with panes for each service. The `-u` flag controls what happens **when the session is first created**:

|              | Without `-u`                                | With `-u`                                         |
| ------------ | ------------------------------------------- | ------------------------------------------------- |
| Server panes | Open to a ready shell                       | Auto-run your start command                       |
| Use case     | Workspaces where you just need code + agent | Main driver where you want servers up immediately |

**After the session is created, `-u` doesn't matter anymore.** You're inside a living zellij session. You manage servers manually from there:

- **Stop a server:** go to the servers tab, Ctrl+C
- **Start a server:** go to the servers tab, type the command (or up-arrow for history)
- **Switch context:** you have multiple zellij sessions open in different terminals. Just switch terminals.

The whole point: every session already has server panes with the right `cwd` set. You never need to close zellij, reopen it, or re-run `hap` just to toggle servers. The panes are there, the shells are there, you just Ctrl+C / type the command.

### Cleanup

```bash
hap clean myproject bugfix         # remove workspace + local branch
hap clean myproject bugfix -D      # also delete remote branch (asks confirmation)
hap clean myproject bugfix -D -y   # skip confirmation
hap clean myproject                # bulk cleanup: removes all inactive workspaces
```

Bulk cleanup skips workspaces that have an active zellij session or a `.hap.gui` lock file (from GUI editors).

### Project management

```bash
hap add myproject /path/to/root    # register manually (hap init does this for you)
hap remove myproject               # unregister (doesn't delete files)
hap list                           # show all registered projects
```

### Editors

```bash
hap open myproject -e cursor
hap open myproject bugfix -e antigravity
```

GUI editors (`cursor`, `antigravity`) use fire-and-forget mode: `hap` creates a `.hap.gui` lock file and exits. The lock protects the workspace from bulk cleanup. Targeted cleanup (`hap clean project workspace`) removes the lock.

## Layout

Default layout file: `config/hap.kdl`. It usually has two tabs:

1. **code** — your editors + agent pane
2. **servers** — server processes, lazygit, and spare shells

Edit `config/hap.kdl` to match your project. The template uses `frontend/` and `backend/` as example `cwd` paths — change them to your actual repo names from `sources/`.

The server panes check the `HAP_UP` env var to decide whether to auto-run. Replace the placeholder `echo` commands with your real start commands. See [templates/hap.kdl](templates/hap.kdl) for the pattern.

### Layout profiles

When one project needs different pane setups (auth+beat vs landing-only, etc.), put named layouts in `config/profiles/` and select them with `-p` / `--profile`:

```
config/
├── hap.kdl                 ← default (used when no -p)
└── profiles/
    ├── auth-beat.kdl
    ├── auth-gain.kdl
    ├── beat-gain.kdl
    └── landing.kdl
```

```bash
hap open myproject -p auth-beat
hap open myproject -p landing -u
```

Resolution:

1. `-p <name>` → `config/profiles/<name>.kdl` (errors if missing)
2. else → `config/hap.kdl` if present
3. else → open zellij with no custom layout

Profiles only change which layout file zellij loads. They do not change which repos get worktrees — every workspace still gets all `sources/`.

## Data

All hap data lives in `~/.local/share/hap/`:

- `projects.csv` — registered projects (name|path)
- `templates/hap.kdl` — layout template (installed by `make install`)

## License

MIT
