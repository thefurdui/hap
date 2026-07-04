# hap

CLI tool for running AI agents in parallel on different git branches. Manages git worktrees, zellij sessions, and server lifecycle across multiple workspaces.

## The Problem

You're working on a feature. An agent is running on it. It takes 20 minutes. You're sitting there. That's 20 minutes gone.

`hap` lets you spin up isolated workspaces — each with its own branch, its own agent, its own terminal session — so you can work on three things at once while agents do the heavy lifting.

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

That's it. `hap init` detects your repos, scaffolds the directory structure, creates worktrees, copies the layout template, and registers the project. You're ready to go.

Then edit `config/hap.kdl` to set your server start commands, and:

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
2. Creates `sources/`, `workspaces/main/`, `config/`, `shared/`
3. Moves each repo into `sources/<name>/`
4. Detaches HEAD in each source repo, creates a worktree in `workspaces/main/<name>/` on the original branch
5. Moves any leftover files/dirs into `misc/`
6. Copies `hap.kdl` template into `config/`
7. Registers the project in `~/.local/share/hap/projects.csv`

**Result:**
```
your-project/
├── config/
│   └── hap.kdl         ← edit this: cwd paths, server commands
├── sources/
│   ├── frontend/       ← detached HEAD, used for worktree ops
│   └── backend/
├── workspaces/
│   └── main/
│       ├── frontend/   ← git worktree (your working copy)
│       └── backend/
├── shared/             ← put .env files, certs, etc. here
└── misc/               ← leftover non-repo files (if any)
```

### Shared State

If you have files that aren't in git but need to exist in every workspace (`.env`, local certs, IDE configs):

1. Create a folder in `shared/` named after the repo: `shared/backend/`
2. Mirror the file's relative path: `shared/backend/.env`
3. `hap` will symlink these into every new workspace automatically

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
```

### Open a workspace

```bash
hap open myproject bugfix          # opens "bugfix", creates it if new
hap open myproject bugfix -u       # same, but auto-start servers
hap open myproject bugfix -B feat/login   # custom branch name
```

What happens when a workspace is created:

1. Creates `workspaces/bugfix/`
2. Adds git worktrees from every repo in `sources/` (branch: `hap/bugfix`)
3. Pushes the branch to origin
4. Installs dependencies in the background (pnpm/go)
5. Symlinks shared state from `shared/`
6. Opens a zellij session

If the workspace already exists, it just opens it.

### Servers and the `-u` flag

Every session gets a "servers" tab with panes for each service. The `-u` flag controls what happens **when the session is first created**:

| | Without `-u` | With `-u` |
|---|---|---|
| Server panes | Open to a ready shell | Auto-run your start command |
| Use case | Workspaces where you just need code + agent | Main driver where you want servers up immediately |

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

There's one layout file: `hap.kdl`. It has two tabs:

1. **code** — your editors + agent pane
2. **servers** — server processes, lazygit, and spare shells

Edit `config/hap.kdl` to match your project. The template uses `frontend/` and `backend/` as example `cwd` paths — change them to your actual repo names from `sources/`.

The server panes check the `HAP_UP` env var to decide whether to auto-run. Replace the placeholder `echo` commands with your real start commands. See [templates/hap.kdl](templates/hap.kdl) for the pattern.

## Data

All hap data lives in `~/.local/share/hap/`:

- `projects.csv` — registered projects (name|path)
- `templates/hap.kdl` — layout template (installed by `make install`)

## License

MIT
