"""FastMCP server for triage agent tools.

Exposes benchmark discovery tools (list, details, resolve) over stdio.
The SkillProvider is constructed from environment variables so credentials
and provider internals never cross the LLM boundary.

Run directly:  python agents/triage/server.py
Connected via: AgentMCPClient (agents/mcp_client.py)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure project root is importable when run as a subprocess.
_project_root = str(Path(__file__).resolve().parents[2])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastmcp import FastMCP

from providers.skills.base import SkillProvider

mcp = FastMCP("triage-agent")

_skill_provider: SkillProvider | None = None


def _build_skill_provider() -> SkillProvider:
    from providers.skills.benchmark_runner import BenchmarkRunnerSkillProvider
    from providers.skills.clusterbuster import ClusterbusterSkillProvider
    from providers.skills.crucible import CrucibleSkillProvider
    from providers.skills.forge import ForgeSkillProvider
    from providers.skills.ioscale import IoscaleSkillProvider
    from providers.skills.k8s_netperf import K8sNetperfSkillProvider
    from providers.skills.kube_burner import KubeBurnerSkillProvider
    from providers.skills.multi import MultiHarnessSkillProvider
    from providers.skills.private import PrivateSkillProvider
    from providers.skills.vstorm import VstormSkillProvider
    from providers.skills.zathras import ZathrasSkillProvider

    crucible_home = os.environ.get("CRUCIBLE_HOME", "/opt/crucible")
    zathras_home = os.environ.get("ZATHRAS_HOME", "")

    harnesses: dict[str, SkillProvider] = {
        "crucible": CrucibleSkillProvider(crucible_home),
        "kube-burner": KubeBurnerSkillProvider(),
        "k8s-netperf": K8sNetperfSkillProvider(),
        "benchmark-runner": BenchmarkRunnerSkillProvider(),
        "clusterbuster": ClusterbusterSkillProvider(),
        "vstorm": VstormSkillProvider(),
        "ioscale": IoscaleSkillProvider(),
        "forge": ForgeSkillProvider(),
    }

    if zathras_home:
        harnesses["zathras"] = ZathrasSkillProvider(zathras_home)
    else:
        private = PrivateSkillProvider()
        zathras_tests = private._load_config("zathras").get("tests")
        if zathras_tests:
            harnesses["zathras"] = ZathrasSkillProvider(fallback_tests=zathras_tests)

    return MultiHarnessSkillProvider(
        harnesses, PrivateSkillProvider(), default_harness="crucible"
    )


def _get_provider() -> SkillProvider:
    global _skill_provider
    if _skill_provider is None:
        _skill_provider = _build_skill_provider()
    return _skill_provider


@mcp.tool()
async def list_benchmarks() -> str:
    """List all available benchmark suites with their descriptions and supported parameters."""
    sp = _get_provider()
    benchmarks = await sp.list_benchmarks()
    return json.dumps(
        [
            {
                "name": b.name,
                "description": b.description,
                "roles": b.roles,
                "min_hosts": b.min_hosts,
                "harness": b.harness,
            }
            for b in benchmarks
        ],
        indent=2,
    )


@mcp.tool()
async def get_benchmark_details(name: str) -> str:
    """Get detailed information about a specific benchmark suite including supported parameters and endpoint types."""
    sp = _get_provider()
    b = await sp.get_benchmark(name)
    if b is None:
        return json.dumps({"error": f"Benchmark '{name}' not found"})
    return json.dumps(
        {
            "name": b.name,
            "description": b.description,
            "supported_params": b.supported_params,
            "roles": b.roles,
            "min_hosts": b.min_hosts,
            "harness": b.harness,
        },
        indent=2,
    )


@mcp.tool()
async def resolve_benchmark(
    description: str,
    workload_type: str = "",
    harness: str = "",
) -> str:
    """Given a natural language description of what the user wants to test, find the best matching benchmark suite. Returns the suite name or null if no match."""
    sp = _get_provider()
    reqs: dict[str, Any] = {
        "description": description,
        "workload_type": workload_type,
    }
    if harness:
        reqs["harness"] = harness

    result = await sp.resolve_benchmark(reqs)
    if result is None:
        return json.dumps({"matched_suite": None})

    capable: list[dict[str, Any]] = []
    if hasattr(sp, "find_capable_harnesses"):
        capable = await sp.find_capable_harnesses(result)
    harnesses_list = [c["harness"] for c in capable]

    response: dict[str, Any] = {
        "matched_suite": result,
        "harnesses": harnesses_list,
    }
    if len(harnesses_list) == 1:
        response["harness"] = harnesses_list[0]
        response["note"] = (
            f"Only '{harnesses_list[0]}' provides this benchmark "
            f"— set harness directive to '{harnesses_list[0]}'"
        )
    elif len(harnesses_list) > 1:
        response["note"] = (
            f"Multiple harnesses offer this benchmark: {harnesses_list}. "
            "Set harness directive if the user specified one, "
            "otherwise the default harness will be used."
        )
    return json.dumps(response, indent=2)


if __name__ == "__main__":
    mcp.run()
