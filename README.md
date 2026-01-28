# hap

**Hive Agent Pilot.** A blunt, efficient project manager for the modern ~~10x~~ Multi-threaded Engineer.

`hap` is a CLI tool designed for developers who want to use **AI Agents** locally in parallel on different git branches. It enforces a "Hive" directory structure to manage complex, multi-repository projects without context switching.

## Why?

Most project managers just `cd` into a folder. `hap` manages **parallel universes**.

1.  **The Hive Structure:** Separates `sources` (git history) from `workspaces` (active state).
2.  **Workspace Mode:** Instantly spawn a temporary, isolated workspace (`hap -w`) for an AI agent or a quick hotfix.
3.  **Explicit Cleanup:** Workspaces persist after you close the editor. Use the dedicated cleanup command to remove them and their branches when done.
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
- Pushes the new branch to `origin` immediately.
- Installs dependencies (pnpm/go) in the background.
- Opens Zellij using `hap-lite.kdl` (No servers, just code + agent).
- **On Exit:** The workspace remains.

**Cleanup:**
When you are done with a task, use the cleanup command.

```bash
hap -c your-project backend-fix      # Clean local workspace & branch
hap -c your-project backend-fix -D   # Clean local + DELETE REMOTE branch (Prompts confirmation)
hap -c your-project                  # Bulk clean all inactive, clean workspaces
```

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

`hap` uses a lightweight "Supervisor Pattern" for managing workspace lifecycles:

1. **PID Lock:** A `.hap.pid` file is created in every workspace upon creation.
2. **Activity Tracking:**
   - **GUI Editors:** The script blocks (via `--wait`) until the editor closes.
   - **Zellij:** The script waits for the Zellij process to exit.
3. **Cleanup:**
   - When the editor exits, the PID file is removed, marking the workspace as "inactive."
   - Running `hap -c <project>` scans for workspaces without a valid PID or Zellij session and cleans them up.
4. **Safety First:** Workspaces with uncommitted changes are always preserved, even during forced cleanup.

### Data Location

All `hap` data is stored in `~/.local/share/hap/`:

- `projects.csv` — Registered projects

## License

MIT