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

Both approaches use the exact same commands. The only difference is whether you run `hap -c` after merging.

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

## Setup

### 1. Create the project structure

```
~/projects/your-project/
├── config/         ← put hap.kdl here (copy from templates/)
├── sources/        ← your git repos (the source of truth)
├── workspaces/     ← managed by hap
│   └── main/       ← your main worktree (create this yourself)
└── shared/         ← (optional) files symlinked into every workspace
```

- **`sources/`** — clone your repos here. These are the bare repos that worktrees branch from.
- **`workspaces/main/`** — your primary worktree. Create it manually with `git worktree add` from each repo in `sources/`.
- **`config/hap.kdl`** — copy `templates/hap.kdl` and edit the `cwd` paths and server start commands to match your repos.
- **`shared/`** — put `.env` files, local certs, or anything not in git here. Mirror the repo directory structure. Files get symlinked into every new workspace automatically.

### 2. Register the project

```bash
cd ~/projects/your-project
hap -s your-project .
```

## Usage

```
hap [options]
  -p <project> [workspace]   Open project or workspace
  -s <name> [path]           Register a project
  -c <name> [workspace]      Cleanup workspace(s)
  -u                         Auto-start servers on session create
  -D                         Delete remote branches too (with -c)
  -y                         Skip confirmation prompts (with -D)
  -e <editor>                zellij (default), cursor, antigravity
  -b <branch>                Base branch for new workspaces (default: dev)
  -B <branch>                Override branch name (default: hap/<workspace>)
  -d <name>                  Unregister a project
  -l                         List registered projects
  -v                         Version
  (no args)                  Interactive project picker (fzf)
```

### Open your project (main driver)

```bash
hap                          # interactive picker
hap -p myproject             # direct, servers tab ready but idle
hap -p myproject -u          # servers auto-start on session create
```

### Open a workspace

```bash
hap -p myproject bugfix      # opens workspace "bugfix", creates it if it doesn't exist
hap -p myproject bugfix -u   # same, but servers auto-start
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
hap -c myproject bugfix        # remove workspace + local branch
hap -c myproject bugfix -D     # also delete remote branch (asks confirmation)
hap -c myproject bugfix -D -y  # skip confirmation
hap -c myproject               # bulk cleanup: removes all inactive workspaces
```

Bulk cleanup skips workspaces that have an active zellij session or a `.hap.gui` lock file (from GUI editors).

### Editors

```bash
hap -p myproject -e cursor
hap -p myproject bugfix -e antigravity
```

GUI editors (`cursor`, `antigravity`) use fire-and-forget mode: `hap` creates a `.hap.gui` lock file and exits. The lock protects the workspace from bulk cleanup. Targeted cleanup (`-c project task`) removes the lock.

## Layout

There's one layout file: `hap.kdl`. It has two tabs:

1. **code** — your editors + agent pane
2. **servers** — server processes, lazygit, and spare shells

Edit `config/hap.kdl` to match your project. The template uses `frontend/` and `backend/` as example `cwd` paths — change them to your actual repo names from `sources/`.

The server panes check the `HAP_UP` env var to decide whether to auto-run. Replace the placeholder `echo` commands with your real start commands. See [templates/hap.kdl](templates/hap.kdl) for the pattern.

## Data

All hap data lives in `~/.local/share/hap/`:

- `projects.csv` — registered projects (name|path)

## License

MIT
