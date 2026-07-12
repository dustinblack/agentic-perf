"""Per-agent command policy enforcement for the infra MCP server.

Defense-in-depth: catches LLM hallucinations that would produce obviously
destructive commands, and prevents trivial bypass via shell interpreters,
command separators, and subshells.

What this catches:
- Destructive global patterns (rm -rf /, mkfs, dd to disk, reboot, etc.)
- Per-agent blocked patterns (iptables flush, forwarding disable, etc.)
- Commands using binaries not in the agent's allowlist
- Shell interpreter bypass: ``bash -c "dangerous_cmd"`` — the payload
  is recursively extracted and re-validated
- Command chaining: ``allowed_cmd; dangerous_cmd`` — each sub-command
  is validated independently
- Subshell injection: ``echo $(dangerous_cmd)`` or backtick equivalents
- Script execution: ``bash script.sh`` — denied because script contents
  are unexamined
- Inline Python: ``python3 -c "..."`` — denied (arbitrary code)

What this does NOT catch (Phase 4 — container/seccomp isolation):
- Base64-encoded payloads
- Obfuscated commands that don't match any pattern
- Commands that are individually safe but dangerous in combination
- Filesystem-level attacks within allowed binaries
"""

from __future__ import annotations

import json
import logging
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

POLICIES_DIR = Path(__file__).parent / "policies"

GLOBAL_BLOCKED_PATTERNS: list[re.Pattern] = [
    re.compile(r"rm\s+-[^\s]*r[^\s]*f\s+/\s*(?:$|--|-\s)"),
    re.compile(r"rm\s+-[^\s]*f[^\s]*r\s+/\s*(?:$|--|-\s)"),
    re.compile(r"mkfs\."),
    re.compile(r"dd\s+.*of\s*=\s*/dev/"),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;"),
    re.compile(r">\s*/dev/sd[a-z]"),
    re.compile(r"\b(shutdown|reboot|halt|poweroff)\b"),
    re.compile(r"\bchmod\s+777\s+/"),
    re.compile(
        r"\bssh\s+.*[\s@](?:localhost|127\.0\.0\.1|::1|0\.0\.0\.0)\b"
        r"|\bssh\s+(?:localhost|127\.0\.0\.1|::1|0\.0\.0\.0)\b"
    ),
]

SHELL_INTERPRETERS = frozenset({"bash", "sh"})
SCRIPT_INTERPRETERS = frozenset({"python3", "python"})
PRIVILEGE_ESCALATORS = frozenset({"sudo"})

_SUBSHELL_RE = re.compile(r"\$\(|`")

_SEPARATOR_RE = re.compile(
    r"""
    (?:^|(?<=\s))  # start or preceded by whitespace
    (?: ;          # semicolon
      | &&         # logical AND
      | \|\|       # logical OR
    )
    (?:\s|$)       # followed by whitespace or end
    """,
    re.VERBOSE,
)


def _split_on_separators(command: str) -> list[str]:
    """Split a command on unquoted ;, &&, || operators.

    Pipe (|) is handled separately — both sides must be
    validated but it's a single pipeline, not chaining.
    """
    parts = []
    current: list[str] = []
    in_single = False
    in_double = False
    i = 0
    chars = command

    while i < len(chars):
        c = chars[i]

        if c == "'" and not in_double:
            in_single = not in_single
            current.append(c)
            i += 1
        elif c == '"' and not in_single:
            in_double = not in_double
            current.append(c)
            i += 1
        elif c == "\\" and i + 1 < len(chars) and (in_double or not in_single):
            current.append(c)
            current.append(chars[i + 1])
            i += 2
        elif not in_single and not in_double:
            if c == ";":
                parts.append("".join(current))
                current = []
                i += 1
            elif c == "&" and i + 1 < len(chars) and chars[i + 1] == "&":
                parts.append("".join(current))
                current = []
                i += 2
            elif c == "|" and i + 1 < len(chars) and chars[i + 1] == "|":
                parts.append("".join(current))
                current = []
                i += 2
            else:
                current.append(c)
                i += 1
        else:
            current.append(c)
            i += 1

    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def _split_on_pipes(command: str) -> list[str]:
    """Split a command on unquoted single | (pipe) operators.

    Does not split on || (logical OR) — that's handled by
    _split_on_separators.
    """
    parts = []
    current: list[str] = []
    in_single = False
    in_double = False
    i = 0
    chars = command

    while i < len(chars):
        c = chars[i]

        if c == "'" and not in_double:
            in_single = not in_single
            current.append(c)
            i += 1
        elif c == '"' and not in_single:
            in_double = not in_double
            current.append(c)
            i += 1
        elif c == "\\" and i + 1 < len(chars) and (in_double or not in_single):
            current.append(c)
            current.append(chars[i + 1])
            i += 2
        elif not in_single and not in_double:
            if (
                c == "|"
                and (i + 1 >= len(chars) or chars[i + 1] != "|")
                and (i == 0 or chars[i - 1] != "|")
            ):
                parts.append("".join(current))
                current = []
                i += 1
            else:
                current.append(c)
                i += 1
        else:
            current.append(c)
            i += 1

    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def _has_unquoted_subshell(command: str) -> bool:
    """Detect $(...) or backtick subshells outside of quotes."""
    in_single = False
    in_double = False
    i = 0

    while i < len(command):
        c = command[i]
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == "\\" and (in_double or not in_single) and i + 1 < len(command):
            i += 2
            continue
        elif not in_single:
            if c == "`":
                return True
            if c == "$" and i + 1 < len(command) and command[i + 1] == "(":
                return True
        i += 1
    return False


def extract_binary(command: str) -> str:
    """Extract the primary binary name from a command string.

    Skips leading env-var assignments (FOO=bar) and returns
    the basename of the first real token.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    for token in tokens:
        if "=" in token and not token.startswith("-"):
            continue
        return Path(token).name
    return ""


@dataclass
class CommandPolicy:
    agent_name: str
    allowed_binaries: set[str] = field(default_factory=set)
    blocked_patterns: list[re.Pattern] = field(default_factory=list)
    max_timeout: int = 7200


def load_policy(agent_name: str) -> CommandPolicy:
    normalized = agent_name.replace("-agent", "").replace("-", "_")
    policy_path = POLICIES_DIR / f"{normalized}.json"
    if not policy_path.exists():
        logger.warning("No policy file for %s, using empty allowlist", agent_name)
        return CommandPolicy(agent_name=agent_name)

    with open(policy_path) as f:
        data: dict[str, Any] = json.load(f)

    agent_blocked = [re.compile(p) for p in data.get("blocked_patterns", [])]

    return CommandPolicy(
        agent_name=agent_name,
        allowed_binaries=set(data.get("allowed_binaries", [])),
        blocked_patterns=agent_blocked,
        max_timeout=data.get("max_timeout", 7200),
    )


def check_command(
    command: str,
    policy: CommandPolicy,
    _depth: int = 0,
) -> tuple[bool, str]:
    """Check a command against a policy.

    Returns (allowed, reason). If allowed is False, reason explains why.
    """
    if _depth > 3:
        return False, "Command nesting too deep"

    command = command.strip()
    if not command:
        return False, "Empty command"

    for pattern in GLOBAL_BLOCKED_PATTERNS:
        if pattern.search(command):
            return False, f"Blocked by global safety pattern: {pattern.pattern}"

    for pattern in policy.blocked_patterns:
        if pattern.search(command):
            return False, f"Blocked by agent policy pattern: {pattern.pattern}"

    if _has_unquoted_subshell(command):
        return False, (
            "Command contains subshell ($() or backticks) — "
            "each command must be submitted separately"
        )

    separator_parts = _split_on_separators(command)
    if len(separator_parts) > 1:
        for part in separator_parts:
            allowed, reason = check_command(part, policy, _depth + 1)
            if not allowed:
                return False, f"Chained sub-command denied: {reason}"
        return True, "OK"

    pipe_parts = _split_on_pipes(command)
    if len(pipe_parts) > 1:
        for part in pipe_parts:
            allowed, reason = check_command(part, policy, _depth + 1)
            if not allowed:
                return False, f"Piped sub-command denied: {reason}"
        return True, "OK"

    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    if not tokens:
        return False, "Empty command after parsing"

    binary = extract_binary(command)

    if not policy.allowed_binaries:
        return False, f"No binaries allowed for agent {policy.agent_name}"

    if binary in SCRIPT_INTERPRETERS:
        return False, (
            f"Interpreter {binary!r} cannot be used directly — "
            f"inline scripts are not validatable"
        )

    if binary in SHELL_INTERPRETERS:
        if "-c" in tokens:
            c_idx = tokens.index("-c")
            if c_idx + 1 < len(tokens):
                payload = tokens[c_idx + 1]
                return check_command(payload, policy, _depth + 1)
            return False, f"{binary} -c with no payload"
        return False, (
            f"{binary!r} without -c is not allowed — "
            f"script file contents cannot be validated"
        )

    if binary in PRIVILEGE_ESCALATORS:
        bin_idx = tokens.index(binary) if binary in tokens else 0
        sub_tokens = tokens[bin_idx + 1 :]
        sub_tokens = [t for t in sub_tokens if not t.startswith("-")]
        if not sub_tokens:
            return False, f"{binary} with no command"
        sub_cmd = " ".join(tokens[bin_idx + 1 :])
        return check_command(sub_cmd, policy, _depth + 1)

    if binary not in policy.allowed_binaries:
        return False, f"Binary {binary!r} not in allowlist for {policy.agent_name}"

    return True, "OK"
