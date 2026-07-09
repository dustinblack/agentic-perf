from __future__ import annotations

import os
from pathlib import Path

AGENTIC_PERF_HOME = Path(
    os.environ.get("AGENTIC_PERF_HOME", Path.home() / ".agentic-perf")
)

CONFIG_PATH = AGENTIC_PERF_HOME / "config.json"
LOG_DIR = AGENTIC_PERF_HOME / "logs"
TICKET_DIR = AGENTIC_PERF_HOME / "tickets"
LOCK_FILE = AGENTIC_PERF_HOME / "orchestrator.pid"
SKILL_CACHE_DIR = AGENTIC_PERF_HOME / "skill-cache"
PLUGIN_SCHEMA_CACHE_DIR = AGENTIC_PERF_HOME / "plugin-schema-cache"
INVESTIGATION_RECORDS_DIR = AGENTIC_PERF_HOME / "investigation-records"
PRICING_PATH = AGENTIC_PERF_HOME / "pricing.yaml"

SECRETS_DIR = Path(
    os.environ.get("AGENTIC_PERF_SECRETS", AGENTIC_PERF_HOME / "secrets")
)
PRIVATE_SKILLS_DIR = Path(
    os.environ.get("AGENTIC_PERF_SKILLS", AGENTIC_PERF_HOME / "private-skills")
)
