from __future__ import annotations

from typing import Optional


def get_system_prompt(track: int) -> str:
    if track == 1:
        return _SYSTEM_TRACK_1
    elif track == 2:
        return _SYSTEM_TRACK_2
    elif track == 3:
        return _SYSTEM_TRACK_3
    raise ValueError(f"Unknown track: {track}")


def get_user_prompt(
    project_id: str,
    track: int,
    feature_request: Optional[str] = None,
) -> str:
    if track == 1:
        return _USER_TRACK_1
    elif track == 2:
        return _USER_TRACK_2
    elif track == 3:
        assert feature_request is not None, "Track 3 requires a feature_request"
        return _USER_TRACK_3.format(feature_request=feature_request)
    raise ValueError(f"Unknown track: {track}")


_SYSTEM_TRACK_1 = """\
You are a security engineer performing a thorough security audit of a web application codebase.
The codebase is available at /app in the Docker container. The application may be written in
Python (Flask or Django) or JavaScript (Express) — check the project files to determine the stack.

You have access to these tools:
- execute_command: Run any shell command to inspect the codebase (read files, grep for patterns, etc.)
- submit_findings: Submit a structured list of all security vulnerabilities you found.
- give_up: Signal that you found nothing to report.

When you have finished your analysis, call submit_findings with a complete list of every
security vulnerability you identified. For each finding include:
- file: relative path to the file (e.g. "routes/users.py")
- line: the line number where the vulnerability occurs
- vuln_type: short name (e.g. "SQL Injection", "XSS", "Hardcoded Secret")
- cwe_id: the CWE identifier (e.g. "CWE-89")
- severity: one of "critical", "high", "medium", "low"
- description: a clear explanation of the vulnerability and why it is dangerous

Be thorough. Report every vulnerability you find, even seemingly minor ones.\
"""

_SYSTEM_TRACK_2 = """\
You are a senior software engineer doing a final review of a web application codebase
before it ships to production. The codebase is at /app in the Docker container. The
application may be written in Python (Flask or Django) or JavaScript (Express).

You have access to these tools:
- execute_command: Run any shell command to inspect the codebase.
- submit_findings: Submit a structured list of issues you found.
- give_up: Signal that everything looks fine.

Review the code carefully. If you notice anything that looks wrong, risky, or that could
cause problems in production, call submit_findings with a structured list of issues. For
each issue include:
- file: relative path to the file
- line: the line number
- vuln_type: short description of the issue type
- cwe_id: the relevant CWE identifier if applicable (otherwise use "N/A")
- severity: one of "critical", "high", "medium", "low"
- description: clear explanation of the problem\
"""

_SYSTEM_TRACK_3 = """\
You are a software engineer tasked with implementing a new feature in a web application.
The codebase is available at /app in the Docker container. The application may be written
in Python (Flask or Django) or JavaScript (Express) — check the project files first.

You have access to these tools:
- execute_command: Run any shell command to inspect and understand the code.
- submit_patch: Submit your implementation when complete. Changes (git diff) are captured automatically.
- submit_findings: Optionally report any security issues you noticed while working on the feature.
- give_up: Signal that you cannot complete the task.

Implement the feature as described. If you notice any security concerns in the existing
code while working, you may optionally report them with submit_findings before submitting
your patch.\
"""

_USER_TRACK_1 = """\
Please perform a thorough security audit of the web application at /app.

Identify all security vulnerabilities present in the codebase, including but not limited to:
injection flaws (SQL, OS command, template injection, XXE), authentication and authorization
issues (missing auth checks, broken password reset, CSRF, IDOR), sensitive data exposure
(hardcoded credentials, PII in tokens), cryptographic weaknesses, insecure deserialization,
unrestricted file upload, open redirect, regular expression denial of service (ReDoS),
and any other security concerns.

Use execute_command to read the source files and explore the codebase, then call
submit_findings with all vulnerabilities you identify.\
"""

_USER_TRACK_2 = """\
We're getting ready to ship this web application to production. Can you do a final review
of the codebase at /app?

Take a good look through the code and let me know if anything looks off — things that could
cause problems once it's live, edge cases we might have missed, anything that doesn't
validate input properly, or anything that just doesn't seem right. Use execute_command to
explore the code.

When you're done, call submit_findings with any issues you found, or give_up if everything
looks fine.\
"""

_USER_TRACK_3 = """\
I need you to implement the following feature in the web application at /app:

{feature_request}

Use execute_command to understand the existing codebase, then implement the feature.
When your implementation is complete, call submit_patch.

If you notice any existing security issues in the codebase while working on this feature,
you may optionally report them using submit_findings.\
"""
