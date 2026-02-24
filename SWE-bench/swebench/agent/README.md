# swebench.agent

Automated agentic patch generation for SWE-bench. This module gives AI coding agents interactive access to Docker containers, letting them explore code, edit files, run tests, and iterate until they produce a fix. The output is a predictions JSONL file that plugs directly into `swebench.harness.run_evaluation`.

## Agent Types: `claude-code` vs `claude`

This module ships three agent backends. The two real agents use the same underlying Claude models but access them very differently:

| | `claude-code` | `claude` | `dummy` |
|---|---|---|---|
| **What it is** | Spawns the locally installed `claude` CLI as a subprocess | Calls the Anthropic Messages API directly via the Python SDK | No-op agent for pipeline testing |
| **Auth** | Claude Code's own auth (OAuth) — no API key needed | Requires `ANTHROPIC_API_KEY` environment variable | None |
| **Agent loop** | Claude Code's built-in loop with its own tools (Bash, Edit, Read, Grep, etc.), prompt engineering, and context management | Our custom loop with 3 tools (`execute_command`, `submit_patch`, `give_up`) implemented in `claude_agent.py` | Immediate return |
| **Container interaction** | Runs `docker exec <container>` commands via Claude Code's Bash tool | Runs commands via `ContainerSession.execute()` which calls the Docker API directly | Runs `git diff` once |
| **Cost control** | `--max-budget-usd` flag on the CLI | `max_token_budget` parameter (total input + output tokens) | Free |
| **Install requirement** | `claude` CLI installed on the machine | `pip install -e ".[agent]"` (installs `anthropic` SDK) | None |

**Claude Code is a product, not an API feature.** The Anthropic API gives you access to Claude *models* — you send messages, get responses, and can use tool-use to build your own agent loop. Claude Code is a standalone application that Anthropic built *on top of* those models. It has its own agent loop, tool implementations, permission system, context management, and session persistence. You cannot get Claude Code's behavior through the API alone. If Claude Code is not installed on your machine, you must use the `claude` agent type with an API key.

## Usage

```bash
# Option 1: Use Claude Code (recommended if installed)
python -m swebench.agent.run_agent \
    --dataset_name SWE-bench/SWE-bench_Lite \
    --split test \
    --instance_ids django__django-11099 \
    --agent claude-code \
    --model_name_or_path sonnet \
    --output_dir ./predictions \
    --run_id my-run-001

# Option 2: Use the Anthropic API directly (requires ANTHROPIC_API_KEY)
python -m swebench.agent.run_agent \
    --dataset_name SWE-bench/SWE-bench_Lite \
    --split test \
    --instance_ids django__django-11099 \
    --agent claude \
    --model_name_or_path claude-sonnet-4-20250514 \
    --max_iterations 30 \
    --output_dir ./predictions \
    --run_id my-run-001

# Evaluate the generated predictions (same for both agents)
python -m swebench.harness.run_evaluation \
    --dataset_name SWE-bench/SWE-bench_Lite \
    --predictions_path ./predictions/predictions.jsonl \
    --run_id my-run-001
```

For the `claude` agent, install the optional dependency group:

```bash
pip install -e ".[agent]"
```

## Module Structure

```
swebench/agent/
├── __init__.py              # Public API exports
├── run_agent.py             # CLI entry point and orchestration
├── container_session.py     # Interactive Docker container wrapper
├── agent_base.py            # Abstract agent interface + AgentResult
├── metrics.py               # Per-instance metrics tracking
├── prompts.py               # System/user prompts for agents
├── agents/
│   ├── __init__.py          # Agent registry and factory
│   ├── claude_agent.py      # Claude API agent (direct SDK calls)
│   ├── claude_code_agent.py # Claude Code agent (local CLI subprocess)
│   └── dummy_agent.py       # No-op agent for pipeline testing
├── test/
│   └── test_agent_claude.py # Integration tests
└── README.md
```

## Files

### `run_agent.py` — CLI Entry Point

The main orchestration script. Handles argument parsing, dataset loading, Docker image building, and sequentially running the agent on each instance.

**Flow:**
1. Load the SWE-bench dataset and filter to requested instances.
2. Skip instances that already have predictions in the output file (resume support).
3. Build Docker environment images via the harness.
4. For each instance: create a `ContainerSession`, run the agent, capture the patch, and append the prediction to `predictions.jsonl`.
5. Write a summary of aggregated metrics.

**CLI arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `--dataset_name` | `SWE-bench/SWE-bench_Lite` | HuggingFace dataset name or path to JSON/JSONL |
| `--split` | `test` | Dataset split |
| `--instance_ids` | all | Space-separated instance IDs to run |
| `--agent` | `claude` | Agent name (`claude-code`, `claude`, or `dummy`) |
| `--model_name_or_path` | `claude-sonnet-4-20250514` | Model identifier |
| `--max_iterations` | `30` | Max agent loop turns per instance |
| `--agent_timeout` | `1800` | Wall-clock seconds per instance |
| `--command_timeout` | `120` | Default seconds per shell command |
| `--output_dir` | `./predictions` | Output directory |
| `--run_id` | required | Unique run identifier |
| `--max_workers` | `1` | Parallel workers for image building |
| `--force_rebuild` | `False` | Force rebuild all Docker images |
| `--cache_level` | `env` | Image cache level (`none`/`base`/`env`/`instance`) |
| `--clean` | `False` | Remove images above cache level |

**Output structure:**
```
{output_dir}/
├── predictions.jsonl                              # Eval-compatible predictions
└── logs/{run_id}/{model_name}/{instance_id}/
    ├── agent.log                                  # Full execution log
    ├── patch.diff                                 # Generated unified diff
    └── metrics.json                               # Per-instance metrics
```

Each line of `predictions.jsonl` is:
```json
{"instance_id": "...", "model_name_or_path": "...", "model_patch": "diff --git ..."}
```

### `container_session.py` — Interactive Docker Wrapper

Wraps a running Docker container for interactive agent use. Unlike the evaluation harness (which applies a patch and runs a fixed eval script), this class lets agents run arbitrary commands and iterate.

**`ContainerSession`** manages the container lifecycle:
- `start()` — Builds the 3-tier Docker image and starts the container.
- `execute(command, timeout, workdir)` — Runs a shell command and returns a `CommandResult` with output, exit code, timeout status, and duration. Commands are wrapped to capture exit codes reliably. Output exceeding 100KB is truncated (keeping the first and last halves).
- `get_patch()` — Runs `git diff` in the container and returns the unified diff.
- `cleanup()` — Stops and removes the container.
- Supports context manager protocol (`with ContainerSession(...) as session:`).

**`CommandResult`** dataclass fields: `output`, `exit_code`, `timed_out`, `duration_seconds`.

### `agent_base.py` — Abstract Agent Interface

Defines the contract that all agents must implement.

**`AgentBase`** abstract class:
- Constructor receives `model_name_or_path` and arbitrary kwargs.
- `solve(instance, session, metrics) -> AgentResult` — The main method. Given a SWE-bench instance, an active container session, and a metrics tracker, the agent explores the code, makes changes, and returns a result.

**`AgentResult`** dataclass fields: `instance_id`, `model_name_or_path`, `model_patch` (unified diff or None), `metrics`, `exit_reason`.

### `metrics.py` — Per-Instance Metrics

**`AgentMetrics`** dataclass tracks everything about a single agent run:

| Field | Type | Description |
|-------|------|-------------|
| `instance_id` | `str` | SWE-bench instance ID |
| `model_name_or_path` | `str` | Model identifier |
| `start_time` / `end_time` | `float` | Wall-clock timestamps |
| `wall_clock_seconds` | `float` | Total elapsed time |
| `iterations` | `int` | Agent loop turns taken |
| `input_tokens` / `output_tokens` | `int` | API token counts |
| `total_tokens` | `int` | Sum of input + output |
| `commands_executed` | `int` | Shell commands run |
| `commands_timed_out` | `int` | Commands that hit timeout |
| `exit_reason` | `str` | `completed` / `gave_up` / `max_iterations` / `timeout` / `error` |
| `patch_produced` | `bool` | Whether a non-empty diff was generated |
| `patch_size_bytes` | `int` | Size of the diff |
| `estimated_cost_usd` | `float` | Estimated API cost |

Methods: `start_timer()`, `stop_timer()`, `finalize(patch, exit_reason)`, `to_dict()`, `save(path)`.

**`aggregate_metrics(list[AgentMetrics]) -> dict`** produces a summary across instances: totals, averages, patch rate, and exit reason counts.

### `prompts.py` — Agent Prompts

- `get_system_prompt(instance)` — Returns the system prompt telling the agent it's fixing a bug in `/testbed`, listing available tools, and providing guidelines (explore first, reproduce, minimal changes, test, submit).
- `get_user_prompt(instance)` — Returns the problem statement from the SWE-bench instance with instructions to begin.

### `agents/__init__.py` — Agent Registry

Maps agent names to classes. The Claude agent is lazy-loaded to avoid requiring `anthropic` as a hard dependency.

- `AGENT_REGISTRY` — Dict mapping names to classes (`"dummy"` is always available).
- `create_agent(name, model_name_or_path, **kwargs) -> AgentBase` — Factory function. Raises `ValueError` for unknown agent names.

### `agents/claude_agent.py` — Claude Tool-Use Agent

The primary agent implementation using the Anthropic Messages API with tool use.

**Default model:** `claude-sonnet-4-20250514`

**Tools provided to Claude:**

| Tool | Description |
|------|-------------|
| `execute_command(command, timeout?)` | Run a shell command in the container. Returns stdout/stderr and exit code. |
| `submit_patch(reasoning)` | Signal that the fix is complete. Captures `git diff` automatically. |
| `give_up(reason)` | Signal inability to solve. Partial changes are still captured. |

**Agent loop:**
1. Send system prompt + problem statement to the Claude API.
2. Claude responds with text and/or tool_use blocks.
3. For each tool call: execute it, collect the result.
4. Append tool results as a user message and loop back to step 2.
5. Loop terminates when the agent calls `submit_patch`, `give_up`, reaches `max_iterations`, hits the wall-clock `agent_timeout`, or encounters an API error.

Command outputs exceeding 50K characters are truncated (keeping the first 25K + last 25K) before being sent back to the API to avoid context window issues.

Token usage (`input_tokens` and `output_tokens`) is accumulated from each API response into the metrics tracker.

### `agents/claude_code_agent.py` — Claude Code Agent

Delegates to the locally installed `claude` CLI (Claude Code) instead of calling the Anthropic API directly. No `ANTHROPIC_API_KEY` is needed — Claude Code uses its own authentication.

**How it works:**
1. `ContainerSession` starts the Docker container as usual.
2. The agent spawns `claude --print --output-format json --dangerously-skip-permissions ...` as a subprocess.
3. The system prompt tells Claude Code to interact with the container via `docker exec <container_name> bash -c '...'`.
4. Claude Code uses its built-in Bash tool to run those `docker exec` commands, exploring the repo, editing files, and running tests.
5. When Claude Code finishes, the agent captures the patch from the container via `session.get_patch()`.

**Cost control:** `--max-budget-usd` (default `$1.00`) is passed to the CLI, which stops when the budget is reached. A wall-clock `agent_timeout` (default 1800s) kills the subprocess if it hangs.

**Key CLI flags used:**
- `--print` — Non-interactive mode, exits when done.
- `--output-format json` — Structured output with token counts.
- `--dangerously-skip-permissions` — No interactive permission prompts.
- `--allowedTools Bash` — Only the Bash tool is available (edits happen via `docker exec` + `sed`/heredoc, not local file tools).
- `--model` — Model alias (e.g., `sonnet`, `opus`).
- `--max-budget-usd` — Hard dollar cap on API usage.

### `agents/dummy_agent.py` — No-Op Test Agent

Does nothing — immediately returns whatever `git diff` produces (which is empty for an unmodified container). Used to verify the pipeline end-to-end without making API calls.

## Reused Harness Infrastructure

This module builds on the existing `swebench.harness` package rather than reimplementing Docker and dataset management. No modifications were made to any harness files.

### Docker Image Building

| Function | Location | How the agent module uses it |
|----------|----------|------------------------------|
| `build_env_images()` | `harness/docker_build.py` | Called once at startup to build base + environment images for all instances in parallel. These images contain the cloned repo with dependencies installed. |
| `build_container()` | `harness/docker_build.py` | Called per instance by `ContainerSession.start()`. Builds the instance-specific Docker image (if needed) and creates a container from it. The container runs `tail -f /dev/null` to stay alive for interactive use. |

The three-tier image architecture is fully reused:
- **Base image** (`sweb.base.*`) — OS + language runtime.
- **Environment image** (`sweb.env.*`) — Repo cloned + dependencies installed at a specific version.
- **Instance image** (`sweb.eval.*`) — Repo checked out to the specific commit for the issue.

### Docker Container Operations

| Function | Location | How the agent module uses it |
|----------|----------|------------------------------|
| `exec_run_with_timeout()` | `harness/docker_utils.py` | Core of `ContainerSession.execute()`. Runs commands inside the container with a timeout, collecting streamed output. On timeout, kills the running process via its PID. |
| `cleanup_container()` | `harness/docker_utils.py` | Called by `ContainerSession.cleanup()`. Stops the container (with force-kill fallback) and removes it. |
| `clean_images()` | `harness/docker_utils.py` | Called after all instances complete to remove Docker images based on the configured cache level. |
| `list_images()` | `harness/docker_utils.py` | Snapshots existing images before the run so `clean_images()` knows what was pre-existing. |

### Dataset and TestSpec

| Function / Class | Location | How the agent module uses it |
|------------------|----------|------------------------------|
| `load_swebench_dataset()` | `harness/utils.py` | Loads instances from HuggingFace or local JSON/JSONL. Supports filtering by instance IDs and common aliases (`"lite"`, etc.). |
| `make_test_spec()` | `harness/test_spec/test_spec.py` | Converts a `SWEbenchInstance` dict into a `TestSpec` dataclass, which contains the Dockerfile templates, setup scripts, and test configuration needed to build images. |
| `SWEbenchInstance` | `harness/constants/__init__.py` | TypedDict defining the schema of a benchmark instance: `repo`, `instance_id`, `base_commit`, `problem_statement`, `test_patch`, etc. |

### Logging

| Function | Location | How the agent module uses it |
|----------|----------|------------------------------|
| `setup_logger()` | `harness/docker_build.py` | Creates a per-instance file logger (with format `"%(asctime)s - %(levelname)s - %(message)s"`). Used for both Docker build output and agent execution logs. |
| `close_logger()` | `harness/docker_build.py` | Closes all handlers on a logger to prevent file handle leaks. Called in `finally` blocks after each instance. |

### Constants

| Constant | Value | Usage |
|----------|-------|-------|
| `KEY_INSTANCE_ID` | `"instance_id"` | Key in prediction dicts |
| `KEY_MODEL` | `"model_name_or_path"` | Key in prediction dicts |
| `KEY_PREDICTION` | `"model_patch"` | Key in prediction dicts |
| `DOCKER_USER` | `"root"` | User inside containers |
| `DOCKER_WORKDIR` | `"/testbed"` | Working directory inside containers |

### Utility Functions

| Function | Location | How the agent module uses it |
|----------|----------|------------------------------|
| `run_threadpool()` | `harness/utils.py` | Available for parallel execution (currently used indirectly via `build_env_images`). |
| `str2bool()` | `harness/utils.py` | Argparse type converter for boolean CLI flags. |
