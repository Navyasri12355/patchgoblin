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
Stage 2: Issue Discovery + Contribution Matching
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

# Inspect an issue (with deterministic difficulty + heuristic fit)
goblin inspect pallets/flask#123

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
Services (discovery.py)
 ↓
Analysis (issue / repository / contributor / matching)
 ↓
GitHub Client (httpx)
 ↓
GitHub REST API
```

**Responsibilities:**

| Layer | Package | Purpose |
|---|---|---|
| CLI | `patchgoblin.cli` | User interface, input parsing, Rich output |
| Services | `patchgoblin.services` | Orchestration and business logic |
| Analysis | `patchgoblin.analysis` | Deterministic heuristics (difficulty, matching) |
| GitHub client | `patchgoblin.github` | All GitHub API communication |
| Domain models | `patchgoblin.models` | Typed Pydantic models |
| Config | `patchgoblin.config` | Environment-based configuration |

The CLI never constructs HTTP requests directly.  
The GitHub client is the only layer that communicates with GitHub.  
Credentials stay inside the GitHub client and never reach analysis or agent logic.

---

## Security

PatchGoblin treats security as a first-class concern:

- Credentials are read from environment variables only — never hardcoded.
- Tokens are never printed, logged, or included in error messages.
- Tokens are never sent to an LLM (not yet introduced, but the architecture enforces separation).
- Stage 2 is strictly **read-only** with respect to GitHub.
- All consequential actions (push, PR creation) require explicit human approval.

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

[ ] LLM-powered issue explanation
[ ] Repository investigation
[ ] Contribution plan generation
[ ] Repository cloning
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
