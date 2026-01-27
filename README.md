# hap

**Hive Agent Pilot.** A blunt, efficient project manager for the modern ~~10x~~ Multi-threaded Engineer.

`hap` is a CLI tool designed for developers who want to use **AI Agents** locally in parallel on different git branches. It enforces a "Hive" directory structure to manage complex, multi-repository projects without context switching.

## Why?

Most project managers just `cd` into a folder. `hap` manages **parallel universes**.

1.  **The Hive Structure:** Separates `sources` (git history) from `workspaces` (active state).
2.  **Workspace Mode:** Instantly spawn a temporary, isolated workspace (`hap -w`) for an AI agent or a quick hotfix.
3.  **Auto-Cleanup:** When you close the session, `hap` checks for uncommitted changes. If clean, it nukes the temporary workspace. No `git stash` required.
4.  **Dual Modes:** Support for Heavy layouts (Servers/DBs) and Lite layouts (Editor only).

## Installation

### Prerequisites

- `bash` (4.0+)
- `zellij` (default editor)
- `fzf`
- `git`
- `cursor` or `antigravity` (optional, for `-e cursor` or `-e antigravity` support)
- `pnpm` (optional, for auto-install)

### Build

```bash
git clone https://github.com/thefurdui/hap.git
cd hap
make install
```

## Usage

### 1. Setup your Project (The Hive)

`hap` requires a specific directory structure to manage parallel contexts effectively.

1.  **Create the Skeleton:**

    ```text
    ~/projects/your-project/
    ├── config/             <-- You MUST put hap.kdl and hap-lite.kdl here
    ├── sources/            <-- Bare or Detached Git Repos (The "Truth")
    ├── workspaces/         <-- Managed by hap (The "Action")
    └── shared/             <-- (Optional) Persistent state linked to workspaces
    ```

2.  **Shared State (Optional):**
    If you have files that are NOT in git (like `.env` files, local certificates, or IDE configs) but need them in every ephemeral workspace:
    - Create a folder in `shared/` named exactly like the repo in `sources/`.
    - Any file placed in `shared/repo-name/` will be automatically symlinked into the workspace when created.

3.  **Configure the Layouts:**
    Copy the files from `templates/` into your `config/` folder and adapt them:
    - **`hap.kdl` (The Heavy Lifter):** Edit the "Systems" tab. Change the `cwd` paths to match your repo names in `sources/` and update the `args` to run your actual servers (e.g., `go run main.go`, `pnpm dev`).
    - **`hap-lite.kdl` (The Agent):** Update the agent pane command if you use something other than `gemini` (e.g., `claude`, `aider`).

4.  **Register the Project:**
    ```bash
    cd ~/projects/your-project
    hap -s your-project .
    ```

### 2. The Workflow

**Daily Driver (Full Mode):**
Opens your project with the servers defined in `hap.kdl` running automatically.

```bash
hap                     # Interactive list
hap -p your-project     # Open directly
```

**Agent / Parallel Mode:**
You are working in Main. You need to fix a bug on the `backend` without stopping the servers or changing branches.

```bash
hap -w your-project backend-fix
```

- Creates `workspaces/backend-fix`.
- Creates fresh git worktrees from `sources/`.
    - Default branch: `hap/backend-fix/repo-name`
- Installs dependencies (pnpm/go) in the background.
- Opens Zellij using `hap-lite.kdl` (No servers, just code + agent).
- **On Exit:** If git status is clean, the workspace self-destructs.

**Target Branch Control:**
You can specify a target branch name instead of the default `hap/` prefix.

```bash
hap -w your-project login-feature -B feat/login
```
- Creates `workspaces/login-feature`.
- Checks out branch `feat/login/repo-name`.

**Manual Mode Selection:**
Open the Main workspace, but skip the heavy server startup (uses `hap-lite.kdl`).

```bash
hap -m lite
```

**Custom Editor:**
By default, `hap` uses Zellij. You can switch to a GUI editor for a more traditional IDE experience.

```bash
hap -p your-project -e cursor
hap -w your-project fix-bug -e cursor
hap -p your-project -e antigravity
hap -w your-project fix-bug -e antigravity
```

Currently supported values for `-e`: `zellij` (default), `cursor`, `antigravity`.

## Architecture

### Supervisor Pattern

`hap` uses a "Supervisor Pattern" for managing workspace lifecycles:

1. **PID Lock (GUI Editors):** When using `cursor` or `antigravity`, a `.hap.pid` file is created in the workspace containing the script's PID. The script blocks (via `--wait`) until the editor closes.

2. **Process Replacement (Zellij):** When using Zellij, the script uses `exec` to replace itself with the Zellij process. No PID file is created since the shell process dies.

3. **Signal Trapping:** Robust `trap` on `EXIT SIGINT SIGTERM SIGHUP` ensures cleanup runs even if:
   - User `Cmd+Q`s the GUI editor
   - Terminal is killed
   - Process receives interrupt signals

4. **Zombie Cleanup (Self-Healing):** On every `hap` invocation, orphaned workspaces are detected and cleaned:
   - Workspaces with `.hap.pid`: Check if PID is alive; if dead, cleanup
   - Workspaces without PID file (Zellij): Check if Zellij session exists; if not, cleanup

5. **Safety First:** Workspaces with uncommitted changes are always preserved.

### Data Location

All `hap` data is stored in `~/.local/share/hap/`:

- `projects.csv` — Registered projects

## License

MIT