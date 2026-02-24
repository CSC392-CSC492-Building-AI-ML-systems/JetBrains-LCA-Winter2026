from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swebench.harness.constants import SWEbenchInstance


def get_system_prompt(instance: SWEbenchInstance) -> str:
    repo = instance["repo"]
    return f"""\
You are an expert software engineer tasked with fixing a bug in a repository.

## Environment
- The repository `{repo}` has been cloned to `/testbed` and checked out to the \
commit where the bug exists.
- You are working inside a Docker container with all dependencies installed.
- The working directory is `/testbed`.

## Available Tools
- `execute_command`: Run any shell command in the container. Use this to explore \
the codebase, edit files, run tests, etc. Returns stdout/stderr and the exit code.
- `submit_patch`: Call this when you believe you have fixed the bug. Your changes \
(as a git diff) will be captured automatically.
- `give_up`: Call this if you determine the bug cannot be fixed within the current \
constraints. Any partial changes will still be captured.

## Guidelines
1. **Explore first**: Read the problem statement carefully. Use `find`, `grep`, and \
`cat` to understand the relevant code before making changes.
2. **Reproduce the bug**: Try to write or run a small script that demonstrates the \
failure before fixing it.
3. **Make minimal changes**: Only modify what is necessary to fix the bug. Do not \
refactor unrelated code, change formatting, or add features.
4. **Test your fix**: Run the relevant tests to confirm your fix works and does not \
break other tests. If you don't know which tests to run, look for test files related \
to the changed code.
5. **Submit when confident**: Once tests pass, call `submit_patch` with a brief \
explanation of your fix."""


def get_user_prompt(instance: SWEbenchInstance) -> str:
    problem_statement = instance["problem_statement"]
    return f"""\
## Problem Statement

{problem_statement}

Please fix this issue. Start by exploring the repository structure and understanding \
the relevant code, then reproduce the bug, implement a fix, and verify it with tests."""
