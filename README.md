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
Stage 3: AI Issue Understanding + Repository Investigation
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

### LLM (for `goblin explain`)

The `explain` command requires an OpenAI-compatible LLM API key.

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

## `inspect` vs `explain`

| Command | Description |
|---|---|
| `goblin inspect OWNER/REPO#N` | **Deterministic** — GitHub issue data, difficulty estimate, heuristic fit score. No LLM. No API key required beyond GitHub. |
| `goblin explain OWNER/REPO#N` | **AI-powered** — Clones the repository, discovers relevant files, calls an LLM, and returns a structured analysis: what the issue means, where it lives in the code, how to approach it, and what is still unknown. |

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
Services (discovery.py / explain.py)
 ↓
Analysis (issue / repository / contributor / matching)   LLM Provider
 ↓                                                           ↑
GitHub Client (httpx)                             Repository Inspector
 ↓                                                           ↑
GitHub REST API                                     Git clone (read-only)
```

**Responsibilities:**

| Layer | Package | Purpose |
|---|---|---|
| CLI | `patchgoblin.cli` | User interface, input parsing, Rich output |
| Services | `patchgoblin.services` | Orchestration: discovery + explain workflows |
| Analysis | `patchgoblin.analysis` | Deterministic heuristics (difficulty, matching) |
| LLM | `patchgoblin.llm` | OpenAI-compatible provider abstraction + prompts |
| Repository | `patchgoblin.repository` | Clone, tree, relevance scoring |
| GitHub client | `patchgoblin.github` | All GitHub API communication |
| Domain models | `patchgoblin.models` | Typed Pydantic models (issues, analysis, etc.) |
| Config | `patchgoblin.config` | Environment-based configuration |

The CLI never constructs HTTP requests directly.  
GitHub credentials and LLM credentials are kept strictly separate.  
Credentials are never included in prompts, logs, or error messages.  
Repository code is never executed — Stage 3 is purely static analysis.

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
- All consequential actions (push, PR creation) require explicit human approval in later stages.

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

[ ] Repository-aware code generation
[ ] Sandboxed coding agent
[ ] Test execution
[ ] Human diff review
[ ] Branch creation
[ ] Branch push
[ ] PR creation
[ ] Maintainer feedback loop
```

Future agentic functionality will follow the principle:

> **AI proposes. Human approves. System executes.**

Every consequential action (pushing code, creating PRs, merging) will require explicit approval
before execution.
