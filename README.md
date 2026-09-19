# PatchGoblin

> Your open-source contribution copilot.

PatchGoblin is the project.  
`goblin` is the CLI.

Install PatchGoblin, then summon it from your terminal with:

```
goblin
```

PatchGoblin helps developers go from _"I don't know where to start"_ to shipping
real open-source patches — with the **human always in control** of consequential actions.

---

## Current Status

```
Stage 5: Sandboxed Test Execution + Branch/PR Workflow
```

---

## Installation

PatchGoblin uses [uv](https://docs.astral.sh/uv/) for dependency and environment management.

```bash
# Clone the repository
git clone https://github.com/yourusername/patchgoblin.git
cd patchgoblin

# Install (creates a virtual environment automatically)
uv sync

# Verify the CLI is available
uv run goblin --help
```

---

## Configuration

### GitHub

PatchGoblin reads your GitHub token from the environment.

1. Create a Personal Access Token at <https://github.com/settings/tokens>  
   (Minimum scope: `public_repo` for read-only access.)

2. Export it in your shell:

```bash
export GITHUB_TOKEN=your_github_token_here
```

3. Verify it works:

```bash
goblin auth status
```

### LLM (for `goblin explain` and `goblin work`)

The `explain` and `work` commands require an OpenAI-compatible LLM API key.

```bash
export LLM_API_KEY=your_llm_api_key_here   # Required
export LLM_BASE_URL=https://api.openai.com/v1  # Optional (default: OpenAI)
export LLM_MODEL=gpt-4o-mini               # Optional (default: gpt-4o-mini)
```

`LLM_BASE_URL` can point to any OpenAI-compatible endpoint, including a local
[Ollama](https://ollama.com) instance at `http://localhost:11434/v1`.

See [`.env.example`](.env.example) for the full list of supported variables.

**Never commit real tokens.** The `.env` file is git-ignored.

---

## Usage

```bash
# Show help
goblin --help

# Check authentication status
goblin auth status

# Display your GitHub profile
goblin profile

# Inspect an issue (deterministic: difficulty estimate + heuristic fit score)
goblin inspect pallets/flask#123

# AI-powered analysis: what the issue means, where to look, how to approach it
goblin explain pallets/flask#123

# Analyze using a specific model
goblin explain --model gpt-4o pallets/flask#123

# Analyze using only GitHub metadata (skip repository cloning)
goblin explain --skip-clone pallets/flask#123

# Stage 4: implement an issue in an isolated workspace
goblin work start pallets/flask#123

# Skip the human-approval prompt (for scripting)
goblin work start --yes pallets/flask#123

# Check status of all PatchGoblin workspaces
goblin work status

# List all workspaces
goblin work list

# Inspect a specific workspace
goblin work inspect pg-7f3a21

# View the full diff for a workspace
goblin work diff pg-7f3a21

# Discard a workspace
goblin work discard pg-7f3a21

# Stage 5: Run sandboxed tests on a workspace
goblin work test pg-7f3a21

# Skip dependency installation (if already cached)
goblin work test pg-7f3a21 --skip-install

# Stage 5: Push branch to remote
goblin work push pg-7f3a21

# Stage 5: Create pull request
goblin work pr pg-7f3a21

# Stage 5: Create as draft PR
goblin work pr pg-7f3a21 --draft

# Stage 5: Get maintainer feedback on PR
goblin work feedback pg-7f3a21

# Find open-source issues matching your contributor profile
goblin find

# Filter by language
goblin find --language python

# Filter by label
goblin find --label good-first-issue
goblin find --label help-wanted

# Limit results
goblin find --limit 5

# Show per-issue signal breakdown
goblin find --verbose

# Combine filters
goblin find --language javascript --min-stars 100 --limit 10
```

---

## Commands

| Command | Description |
|---|---|
| `goblin inspect OWNER/REPO#N` | **Deterministic** — GitHub issue data, difficulty estimate, heuristic fit score. No LLM. No API key required beyond GitHub. |
| `goblin explain OWNER/REPO#N` | **AI-powered** — Clones the repository, discovers relevant files, calls an LLM, returns structured analysis. |
| `goblin work start OWNER/REPO#N` | **Stage 4** — Analyses the issue, asks for human approval, then modifies a disposable isolated workspace and generates a diff for review. |
| `goblin work test TASK-ID` | **Stage 5** — Runs sandboxed tests on a workspace with explicit human approval. |
| `goblin work push TASK-ID` | **Stage 5** — Creates a branch, commits changes, and pushes to remote with explicit human approval. |
| `goblin work pr TASK-ID` | **Stage 5** — Creates a pull request with explicit human approval. |
| `goblin work feedback TASK-ID` | **Stage 5** — Fetches and displays maintainer feedback (read-only). |

### Stage 4 workflow

```
goblin work start owner/repo#123
        │
        ▼
Fetch issue + repository
        │
        ▼
Generate analysis + implementation plan
        │
        ▼
Show plan — ask for human approval
        │
   ┌────┴────┐
   │         │
  NO        YES
   │         │
   ▼         ▼
 Stop    Create isolated workspace
              │
              ▼
         Clone repo
              │
              ▼
       LLM coding agent
              │
              ▼
         Modify files
              │
              ▼
        Generate diff
              │
              ▼
         Show summary
```

> **PatchGoblin never modifies the user's original repository during Stage 4.**

Stage 4 does **not**:

- execute repository code
- run tests against the target repository
- install dependencies
- push to any remote
- create pull requests
- commit changes
- modify GitHub in any way

The user must review the diff and take any further action manually.

### Stage 5 workflow

```
goblin work diff pg-7f3a21  (Stage 4 output)
        │
        ▼
Human approval: run tests?
        │
   ┌────┴────┐
   │         │
  NO        YES
   │         │
   ▼         ▼
 Stop    Sandboxed dependency install
              │
              ▼
        Sandboxed test execution
              │
              ▼
        Show test results
              │
              ▼
Human approval: push branch?
        │
   ┌────┴────┐
   │         │
  NO        YES
   │         │
   ▼         ▼
 Stop    Create PatchGoblin branch
              │
              ▼
         Commit changes
              │
              ▼
        Push to remote
              │
              ▼
Human approval: open PR?
        │
   ┌────┴────┐
   │         │
  NO        YES
   │         │
   ▼         ▼
 Stop    Create pull request
              │
              ▼
        Show maintainer feedback (read-only)
```

> **PatchGoblin only executes repository code inside a hardened, credential-free sandbox, and only after explicit approval. Pushing and opening a PR each require their own separate, explicit approval. PatchGoblin never merges anything.**

Stage 5 adds:

- **Sandboxed test execution** — Runs repository tests in an isolated, resource-limited environment
- **Structured test analysis** — Parses test output and provides summaries
- **Branch creation** — Creates PatchGoblin-owned branches with safe naming
- **Branch push** — Pushes branches only after explicit human approval
- **PR creation** — Creates pull requests only after explicit human approval
- **Feedback polling** — Fetches maintainer feedback (read-only, no automated responses)

Each step requires separate human approval. Approving one step never implicitly approves the next.

`explain` analysis is:

- **read-only** — PatchGoblin never modifies repository files.
- **non-executing** — no repository code is run.
- **commit-pinned** — the analysis records the repository HEAD SHA so you know exactly what state was analyzed.
- **advisory** — AI analysis may contain uncertainty; always review before acting.

---

## How Heuristic Fit Works

PatchGoblin uses **deterministic heuristics** (not an LLM) to estimate how well an issue
matches your contributor profile.

Every fit score is accompanied by the signals that produced it, so you can judge the
estimate yourself.

**Positive signals:**

| Signal | Description |
|---|---|
| Language match | Repository uses a language in your public repos |
| `good first issue` label | Explicitly marked beginner-friendly |
| `help wanted` label | Maintainer is actively seeking contributions |
| Documentation / typo issue | Typically lower barrier to entry |
| Test-related issue | Good way to learn a codebase |
| Clear description | Requirements are visible in the issue body |
| Beginner difficulty estimate | Combination of signals suggests low complexity |

**Negative signals:**

| Signal | Description |
|---|---|
| Advanced difficulty estimate | Architecture, security, or complexity signals |
| No description | Requirements may be unclear |
| Epic / large feature label | Scope is likely very broad |
| Security-sensitive label | Higher risk and context required |
| Long discussion thread | Issue may be contested or complex |

Scores are normalised to **0–100** and labelled as a _heuristic fit_, not an objective measure.
The human chooses the issue — PatchGoblin reduces the search space.

---

## Architecture

```
CLI (goblin)
 ↓
Services (discovery / explain / work / test / push / pr / feedback)
 ↓
Analysis (issue / repository / contributor / matching)   LLM Provider
 ↓                                                           ↑
GitHub Client (httpx)                             Workspace Manager
 ↓                                                           ↑
GitHub REST API                              Coding Agent (structured edits)
                                                             ↑
                                                  Repository Inspector
                                                             ↑
                                               Git clone (isolated workspace)
                                                             ↑
                                                Sandbox (Stage 5: execution)
                                                             ↑
                                            Testing (Stage 5: language detection, test execution)
                                                             ↑
                                            Git (Stage 5: branch, push operations)
```

**Responsibilities:**

| Layer | Package | Purpose |
|---|---|---|
| CLI | `patchgoblin.cli` | User interface, input parsing, Rich output |
| Services | `patchgoblin.services` | Orchestration: discovery / explain / work / test / push / pr / feedback |
| Analysis | `patchgoblin.analysis` | Deterministic heuristics (difficulty, matching) |
| LLM | `patchgoblin.llm` | OpenAI-compatible provider abstraction + prompts |
| Coding | `patchgoblin.coding` | Coding agent, file editor, context builder |
| Workspace | `patchgoblin.workspace` | Workspace creation, metadata, path safety |
| Repository | `patchgoblin.repository` | Clone, tree, relevance scoring, git helpers |
| GitHub client | `patchgoblin.github` | All GitHub API communication |
| Sandbox | `patchgoblin.sandbox` | Sandboxed code execution with resource limits (Stage 5) |
| Testing | `patchgoblin.testing` | Language detection, test execution, result parsing (Stage 5) |
| Git | `patchgoblin.git` | Branch creation, push operations (Stage 5) |
| Domain models | `patchgoblin.models` | Typed Pydantic models (issues, analysis, etc.) |
| Config | `patchgoblin.config` | Environment-based configuration |

The CLI never constructs HTTP requests directly.
GitHub credentials and LLM credentials are kept strictly separate.
Credentials are never included in prompts, logs, or error messages.
Repository code is never executed outside the sandbox.
Workspace modifications are strictly isolated — the user's original repository is never touched.
Stage 5 adds three explicit approval gates: test execution, branch push, and PR creation.

---

## Security

PatchGoblin treats security as a first-class concern:

- Credentials are read from environment variables only — never hardcoded.
- Tokens are never printed, logged, or included in error messages.
- GitHub tokens and LLM API keys are never sent across the boundary between subsystems.
- GitHub issue content and repository files are treated as **untrusted input** — they are
  clearly delimited in every LLM prompt and the model is instructed not to follow instructions
  embedded in them (prompt injection defense).
- Repository investigation is **read-only** — no code is executed, no packages installed,
  no build scripts run.
- **Stage 5 sandboxing** — Repository code is only executed inside a hardened, credential-free sandbox
  with resource limits (CPU, memory, time, disk, process count) and no network access except for
  explicitly allow-listed package installation.
- All consequential actions (push, PR creation) require explicit human approval at each step.
- PatchGoblin never merges anything, force-pushes, or performs any destructive Git operations.
- Branch naming follows a strict `patchgoblin/` prefix convention to prevent conflicts with user branches.
- Protected branches (main, master, develop, etc.) are never modified by PatchGoblin.

---

## Roadmap

```
[x] CLI scaffold
[x] GitHub client foundation
[x] Basic GitHub authentication
[x] Basic issue inspection
[x] CI
[x] Issue discovery
[x] Basic difficulty estimation
[x] Contributor profile signals
[x] Contribution-fit heuristic
[x] LLM issue explanation
[x] Repository investigation
[x] Relevant-file discovery
[x] Implementation planning
[x] Isolated workspaces
[x] Repository-aware code modification
[x] Diff generation
[x] Human modification approval
[x] Human diff review
[x] Sandboxed test execution
[x] Automated test analysis
[x] Branch creation
[x] Branch push
[x] PR creation
[x] Maintainer feedback loop (read-only)

[ ] Automated response to review comments
[ ] Auto-merge (explicitly out of scope / may never be built)
[ ] Multi-repository batch workflows
```

Future agentic functionality will follow the principle:

> **AI proposes. Human approves. System executes.**

Every consequential action (pushing code, creating PRs, merging) will require explicit approval
before execution.
