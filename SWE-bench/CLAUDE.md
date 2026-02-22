# SWE-bench Repository Guide

## Overview

SWE-bench is a benchmark for evaluating large language models (LLMs) on real-world software engineering tasks. It challenges AI systems to resolve actual GitHub issues by generating code patches. The benchmark supports multiple programming languages (Python, JavaScript, Go, Java, C, PHP, Ruby, Rust) and uses Docker-based containerized evaluation for reproducibility.

Published at ICLR 2024 (Oral) and ICLR 2025. Current version: **4.1.0**.

## Project Structure

```
SWE-bench/
├── swebench/                  # Main Python package
│   ├── harness/               # Evaluation framework
│   ├── collect/               # Data collection pipeline
│   ├── inference/             # Model inference
│   ├── versioning/            # Repository version management
│   └── resources/             # Resource files (original benchmark data)
├── tests/                     # Test suite
├── docs/                      # Documentation site (MkDocs)
├── pyproject.toml             # Project config and dependencies
├── mkdocs.yml                 # Documentation site config
├── CHANGELOG.md               # Version history
└── README.md                  # Project overview
```

---

## Core Modules

### `swebench/harness/` — Evaluation Framework

The core of SWE-bench. Runs model-generated patches inside Docker containers, executes tests, and grades results.

| File | Purpose |
|------|---------|
| `run_evaluation.py` | **Main entry point.** Orchestrates the full evaluation pipeline: loads predictions, builds Docker images, runs tests in containers, collects results. |
| `docker_build.py` | Builds three tiers of Docker images: base (OS + language), env (repo + dependencies at a version), and instance (specific issue setup). |
| `docker_utils.py` | Low-level Docker operations: run containers, copy files into containers, execute commands with timeouts, cleanup. |
| `grading.py` | Evaluates test output logs. Computes FAIL_TO_PASS (tests that should now pass) and PASS_TO_PASS (tests that must not regress). Determines `ResolvedStatus` (NO/PARTIAL/FULL). |
| `reporting.py` | Generates JSON evaluation reports and summary statistics from grading results. |
| `prepare_images.py` | Pre-builds Docker images before running evaluation (useful for batch preparation). |
| `remove_containers.py` | Cleans up Docker containers after evaluation runs. |
| `utils.py` | Shared utilities: thread pool execution (`run_threadpool`), logging, file helpers. |

**Subdirectories:**

| Directory | Purpose |
|-----------|---------|
| `constants/` | Per-language configuration. Each file (`python.py`, `java.py`, `go.py`, `javascript.py`, `c.py`, `php.py`, `ruby.py`, `rust.py`) defines repo-to-version mappings, install commands, test commands, and environment setup for supported repositories. `fixtures/` contains static test data. |
| `dockerfiles/` | Dockerfile templates per language (`python.py`, `java.py`, etc.). Each generates Dockerfiles for base, env, and instance images for that language's ecosystem. |
| `log_parsers/` | Per-language test output parsers (`python.py`, `java.py`, etc.). Each parses the test framework output (pytest, JUnit, go test, etc.) into structured `TestStatus` results (PASSED/FAILED/SKIPPED/ERROR). |
| `test_spec/` | Test specification creation. `test_spec.py` is the main file — builds `TestSpec` objects that describe how to set up and run tests for each instance. `create_scripts.py` generates shell scripts for repo setup, environment setup, and evaluation. `python.py` and `javascript.py` have language-specific logic. `utils.py` provides helpers. |
| `modal_eval/` | Cloud-based evaluation using [Modal](https://modal.com). `run_evaluation_modal.py` and `run_evaluation_modal_entrypoint.py` handle remote container execution. |

### `swebench/collect/` — Data Collection Pipeline

Collects task instances from GitHub repositories by extracting pull requests that fix issues, paired with their test patches.

| File | Purpose |
|------|---------|
| `print_pulls.py` | Fetches pull request metadata from GitHub repositories using the GitHub API. Extracts PR descriptions, linked issues, diffs, and test changes. |
| `build_dataset.py` | Converts raw PR data into SWE-bench task instances. Matches PRs to issues, extracts test patches, validates instances. |
| `build_dataset_ft.py` | Creates fine-tuning datasets from task instances for model training. |
| `get_tasks_pipeline.py` | End-to-end automation: takes a list of repos and runs the full collection pipeline (fetch PRs → build dataset). |
| `get_top_pypi.py` | Fetches top PyPI packages to identify candidate repositories for benchmark inclusion. |
| `utils.py` | Shared utilities for the collection pipeline. |
| `run_get_tasks_pipeline.sh` | Shell script wrapper for `get_tasks_pipeline.py`. |
| `run_build_dataset_ft.sh` | Shell script wrapper for `build_dataset_ft.py`. |

**Subdirectories:**

| Directory | Purpose |
|-----------|---------|
| `make_lite/` | Creates the SWE-bench Lite subset. `make_lite.py` selects instances based on criteria defined in `criteria.py`. |
| `make_repo/` | Repository mirroring utilities. `make_repo.sh` and `call_make_repo.py` handle cloning/mirroring repos. |
| `cleanup/` | Maintenance scripts. `delete_gh_workflows.py` removes GitHub workflow files; `remove_envs.py` cleans up conda environments. |

### `swebench/inference/` — Model Inference

Runs LLMs to generate patches for benchmark instances.

| File | Purpose |
|------|---------|
| `run_api.py` | Inference via cloud APIs (OpenAI GPT models, Anthropic Claude models). Sends problem statements to models and collects generated patches. Supports multiple model families. |
| `run_llama.py` | Inference with locally-hosted Llama models. Handles model loading, tokenization, and generation. |
| `run_live.py` | Live inference pipeline for real-time evaluation. |
| `codellama_device_maps.json` | GPU device mapping configuration for CodeLlama models. |

**Subdirectories:**

| Directory | Purpose |
|-----------|---------|
| `make_datasets/` | Dataset preparation for inference. `create_instance.py` creates SWE-bench instances; `create_text_dataset.py` generates text datasets; `bm25_retrieval.py` implements BM25-based code retrieval; `eval_retrieval.py` evaluates retrieval quality; `tokenize_dataset.py` handles tokenization. |
| `llamao/` | Llama-specific optimizations. `modeling_flash_llama.py` implements Flash Attention for Llama; `distributed_attention.py` handles distributed attention computation. |

### `swebench/versioning/` — Version Management

Extracts and manages version information for the repositories in the benchmark.

| File | Purpose |
|------|---------|
| `get_versions.py` | Core version extraction logic. `get_version()` fetches a specific version; `get_versions_from_build()` extracts from build files; `get_versions_from_web()` from web sources; `map_version_to_task_instances()` maps versions to task instances. |
| `constants.py` | Maps repositories to their version file paths (`MAP_REPO_TO_VERSION_PATHS`) and version regex patterns (`MAP_REPO_TO_VERSION_PATTERNS`). |
| `utils.py` | Utilities including `split_instances()` for partitioning instances by version. |
| `run_get_versions.sh` | Shell script wrapper for batch version extraction. |

**Subdirectories:**

| Directory | Purpose |
|-----------|---------|
| `extract_web/` | Web-based version extraction scripts for specific repos (`get_versions_astropy.py`, `get_versions_matplotlib.py`, `get_versions_xarray.py`, etc.). |

---

## Key Entry Points

**Evaluation** (main workflow):
```bash
python -m swebench.harness.run_evaluation \
  --dataset_name <dataset> \
  --predictions_path <path> \
  --max_workers <num> \
  --run_id <id>
```

**Data Collection:**
```bash
python -m swebench.collect.print_pulls <repo> <output.jsonl>
python -m swebench.collect.build_dataset <input.jsonl> <output.jsonl>
python -m swebench.collect.get_tasks_pipeline  # end-to-end
```

**Inference:**
```bash
python -m swebench.inference.run_api      # Cloud API models
python -m swebench.inference.run_llama    # Local Llama models
python -m swebench.inference.run_live     # Live inference
```

---

## Evaluation Pipeline (End-to-End)

This section describes the full flow from a model's prediction to a final score.

### 1. Prediction Format

Models produce predictions as a JSON/JSONL file. Each prediction is a dict with these keys:

```json
{
  "instance_id": "django__django-11099",
  "model_name_or_path": "claude-3-opus",
  "model_patch": "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py\n@@ -10,7 +10,7 @@\n- old_line\n+ new_line\n"
}
```

- **`instance_id`**: Matches a task instance in the benchmark dataset.
- **`model_name_or_path`**: Identifier for the model (used for organizing log directories).
- **`model_patch`**: A **unified diff** (the same format as `git diff` output). This is the model's proposed fix. Can be `null` or empty string if the model produced no patch.

The evaluation harness loads predictions via `get_predictions_from_file()` in `harness/utils.py`, which accepts JSONL files or HuggingFace dataset paths.

### 2. Repository Version Setup

Each task instance is pinned to a specific repository at a specific commit. The setup is defined by `MAP_REPO_VERSION_TO_SPECS` in `harness/constants/` (one file per language). For a given repo + version, the specs dict contains:

- **`python`**: Python version to use (e.g., `"3.9"`)
- **`packages`** / **`install`**: Dependencies and install commands (e.g., `"pip install -e ."`)
- **`test_cmd`**: The command to run tests (e.g., `"pytest tests/"`)
- **`pre_install`** / **`pre_test`**: Commands to run before install/test phases

The `TestSpec` dataclass (`harness/test_spec/test_spec.py`) assembles three shell scripts from these specs:

1. **`install_repo_script`** (`repo_script_list`): Clones the repo, checks out the base commit, sets up the working directory at `/testbed`.
2. **`setup_env_script`** (`env_script_list`): Installs the correct language runtime, creates a virtual environment, installs dependencies.
3. **`eval_script`** (`eval_script_list`): Applies the gold test patch, runs the test command, captures output between `START_TEST_OUTPUT` / `END_TEST_OUTPUT` markers.

These scripts are generated by `harness/test_spec/create_scripts.py` with language-specific logic in `python.py` and `javascript.py`.

### 3. Docker Setup (Three-Tier Image Architecture)

Evaluation uses a layered Docker image strategy for efficiency — shared layers are cached so only instance-specific work is repeated per evaluation.

**Tier 1: Base Image** (`sweb.base.<lang>.<arch>`)
- Built from a minimal OS image (Ubuntu/Debian)
- Installs the language runtime (Python, Node.js, Go, Java, etc.)
- Installs basic system dependencies (git, build tools)
- Generated by `harness/dockerfiles/<lang>.py` → `get_dockerfile_base()`

**Tier 2: Environment Image** (`sweb.env.<lang>.<arch>.<hash>`)
- Built on top of the base image
- Clones the repository at the correct commit
- Installs project dependencies (pip install, npm install, etc.)
- Runs the `setup_env.sh` script inside the container
- The image key includes a hash of the environment script, so changing deps triggers a rebuild
- Generated by `get_dockerfile_env()`

**Tier 3: Instance Image** (`sweb.eval.<arch>.<instance_id>`)
- Built on top of the environment image
- Runs the `setup_repo.sh` script to finalize repo state
- This is the image used to create the evaluation container
- Generated by `get_dockerfile_instance()`

Image building is handled by `docker_build.py`:
- `build_base_images()` → `build_env_images()` → `build_instance_image()` (called sequentially per tier)
- Images are built in parallel across instances using `run_threadpool()`
- Existing images are reused unless `--force_rebuild` is set

### 4. Test Execution

The `run_instance()` function in `run_evaluation.py` handles a single instance:

1. **Start container**: Creates and starts a Docker container from the instance image. The container runs `tail -f /dev/null` to stay alive.

2. **Apply the model patch**: The model's diff is written to a local file, copied into the container at `/tmp/patch.diff`, and applied using one of three strategies (tried in order):
   - `git apply --verbose`
   - `git apply --verbose --reject`
   - `patch --batch --fuzz=5 -p1 -i`

   If all three fail, the instance is marked as failed (`APPLY_PATCH_FAIL`).

3. **Record pre-test git diff**: Captures `git diff` to detect if tests themselves modify the repo.

4. **Run the eval script**: The `eval_script` (generated from the TestSpec) is copied into the container and executed via `/bin/bash /eval.sh`. This script:
   - Applies the gold test patch (the tests that should validate the fix)
   - Runs the test command (e.g., `pytest`, `go test`, `mvn test`)
   - Wraps output between `<<< START_TEST_OUTPUT >>>` and `<<< END_TEST_OUTPUT >>>` markers

5. **Capture output**: Test stdout/stderr is written to `test_output.txt` in the log directory. A configurable timeout (default 1800 seconds) kills the container if tests hang.

6. **Cleanup**: The container is stopped and removed. Images may be removed depending on `--cache_level`.

Multiple instances run in parallel via `run_threadpool()` with `--max_workers` controlling concurrency.

### 5. Grading and Scoring

Grading happens in `harness/grading.py` after test execution:

**Step 1: Parse test output** (`get_logs_eval()`)
- Reads the `test_output.txt` log file
- Checks for error markers (patch apply failure, test errors, timeouts)
- Extracts content between `START_TEST_OUTPUT` / `END_TEST_OUTPUT` markers
- Passes the content to a **language-specific log parser** from `harness/log_parsers/` (e.g., Python's parser reads pytest output, Java's reads JUnit/Maven output)
- Returns a **status map**: `{test_name: TestStatus}` where `TestStatus` is one of `PASSED`, `FAILED`, `SKIPPED`, `ERROR`, `XFAIL`

**Step 2: Compare against gold results** (`get_eval_tests_report()`)

Each task instance has two lists of test names:
- **`FAIL_TO_PASS`**: Tests that were failing on the base commit (before the fix). A correct patch should make these pass.
- **`PASS_TO_PASS`**: Tests that were passing on the base commit. A correct patch must not break these.

The grading compares the eval status map against these lists:

| Category | Test was... | After patch it should... | Result |
|----------|-------------|--------------------------|--------|
| F2P success | Failing | Now passes | Resolution |
| F2P failure | Failing | Still fails | Not resolved |
| P2P success | Passing | Still passes | No regression |
| P2P failure | Passing | Now fails | Regression |

**Step 3: Determine resolution status** (`get_resolution_status()`)

```
f2p_rate = FAIL_TO_PASS successes / total FAIL_TO_PASS tests
p2p_rate = PASS_TO_PASS successes / total PASS_TO_PASS tests

if f2p_rate == 1.0 AND p2p_rate == 1.0 → FULL (resolved)
if 0 < f2p_rate < 1.0 AND p2p_rate == 1.0 → PARTIAL
otherwise → NO
```

An instance counts as **resolved** only if status is `FULL` — all previously-failing tests now pass AND no previously-passing tests regress.

**Step 4: Generate reports** (`reporting.py` → `make_run_report()`)

The final report JSON aggregates across all instances:
- `resolved_ids`: Instances fully resolved
- `unresolved_ids`: Instances that completed but were not resolved
- `error_ids`: Instances that failed to run (build errors, timeouts, patch apply failures)
- `empty_patch_ids`: Instances where the model produced no patch
- `completed_instances` / `total_instances`: Overall completion stats

The **benchmark score** is: `len(resolved_ids) / total_instances` — the percentage of instances fully resolved.

---

## Key Concepts

- **Task Instance**: A single benchmark item — a GitHub issue + its repo at a specific version + test patch that validates the fix.
- **FAIL_TO_PASS**: Tests that were failing before the fix and should pass after. This is the primary success metric.
- **PASS_TO_PASS**: Tests that were passing before and must continue to pass (no regressions).
- **ResolvedStatus**: `FULL` (all FAIL_TO_PASS pass + no regressions), `PARTIAL` (some pass), `NO` (none pass).
- **TestSpec**: A specification object that describes how to set up the repo, install dependencies, apply a patch, and run tests for a given instance.
- **Three-tier Docker images**: `base` (OS + language runtime) → `env` (repo + dependencies at a version) → `instance` (specific issue applied).

---

## Dependencies

**Core:** beautifulsoup4, chardet, datasets (HuggingFace), docker, ghapi, GitPython, modal, python-dotenv, requests, rich, tenacity, tqdm, unidiff

**Optional groups** (defined in `pyproject.toml`):
- `datasets`: transformers, openai, anthropic, tiktoken, jedi, protobuf, sentencepiece
- `inference`: torch, peft, flash_attn, triton
- `test`: pytest, pytest-cov
- `docs`: mkdocs, mkdocs-material, mkdocstrings

---

## Testing

```bash
pytest                        # Run all tests
pytest --exitfirst --cov      # Run with coverage, stop on first failure
```

| Test File | What It Tests |
|-----------|---------------|
| `tests/test_cli.py` | CLI interface and argument parsing |
| `tests/test_collect_cli.py` | Data collection CLI commands |
| `tests/test_evaluation.py` | Evaluation pipeline end-to-end |
| `tests/test_harness_utils.py` | Harness utility functions |
| `tests/test_log_parsers_java.py` | Java test output log parsing |
| `tests/test_data/` | Test fixtures and sample data |

CI runs on GitHub Actions (`.github/workflows/pytest.yaml`) — Ubuntu, Python 3.10, using `uv` as the package manager.

---

## Available Datasets

| Dataset | Description |
|---------|-------------|
| SWE-bench | Full benchmark (~2,300 instances) |
| SWE-bench Lite | Smaller, curated subset |
| SWE-bench Verified | 500 human-verified solvable instances |
| SWE-bench Multimodal | Visual software domain instances |

Datasets are hosted on HuggingFace and loaded via the `datasets` library.
