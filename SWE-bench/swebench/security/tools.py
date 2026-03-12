from __future__ import annotations

TOOL_EXECUTE_COMMAND = {
    "name": "execute_command",
    "description": (
        "Execute a shell command in the Docker container at /app. "
        "Returns the command output (stdout+stderr) and exit code."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Optional timeout in seconds. Defaults to 120.",
            },
        },
        "required": ["command"],
    },
}

TOOL_SUBMIT_FINDINGS = {
    "name": "submit_findings",
    "description": (
        "Submit a structured list of security vulnerabilities or issues found "
        "in the codebase. Call this when you have completed your analysis."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "description": "List of vulnerability findings.",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "description": "Relative file path (e.g. 'routes/users.py').",
                        },
                        "line": {
                            "type": "integer",
                            "description": "Line number where the vulnerability occurs.",
                        },
                        "vuln_type": {
                            "type": "string",
                            "description": "Short vulnerability name (e.g. 'SQL Injection').",
                        },
                        "cwe_id": {
                            "type": "string",
                            "description": "CWE identifier (e.g. 'CWE-89').",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"],
                        },
                        "description": {
                            "type": "string",
                            "description": "Explanation of the vulnerability.",
                        },
                    },
                    "required": [
                        "file", "line", "vuln_type", "cwe_id", "severity", "description"
                    ],
                },
            },
        },
        "required": ["findings"],
    },
}

TOOL_SUBMIT_PATCH = {
    "name": "submit_patch",
    "description": (
        "Submit your implementation. Call this when the feature is complete. "
        "Your changes (git diff) will be captured automatically."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of the implementation.",
            },
        },
        "required": ["reasoning"],
    },
}

TOOL_GIVE_UP = {
    "name": "give_up",
    "description": "Signal that you cannot complete the task.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Why you are giving up.",
            },
        },
        "required": ["reason"],
    },
}


def get_tools_for_track(track: int) -> list[dict]:
    """Return the tool list for a given track."""
    if track in (1, 2):
        return [TOOL_EXECUTE_COMMAND, TOOL_SUBMIT_FINDINGS, TOOL_GIVE_UP]
    elif track == 3:
        return [TOOL_EXECUTE_COMMAND, TOOL_SUBMIT_FINDINGS, TOOL_SUBMIT_PATCH, TOOL_GIVE_UP]
    raise ValueError(f"Unknown track: {track}")
