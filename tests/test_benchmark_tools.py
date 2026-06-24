from __future__ import annotations

import pytest

from agents.benchmark.mcp_server import create_benchmark_tool_handlers
from providers.skills.base import RunfileTemplate
from tests.conftest import MockSkillProvider


@pytest.fixture
def mock_provider() -> MockSkillProvider:
    return MockSkillProvider(
        private_config={
            "crucible": {
                "execution": {
                    "controller_required": True,
                    "run_command": "crucible run",
                    "endpoint_type": "remotehosts",
                    "endpoint_user": "root",
                    "default_userenv": "alma8",
                    "default_osruntime": "podman",
                    "pre_run": ["ssh_key_setup"],
                    "run_file_format": "json",
                    "results_dir_pattern": "/var/lib/crucible/run/*",
                },
            },
            "zathras": {
                "execution": {
                    "controller_required": True,
                    "run_command": "/opt/zathras/bin/burden",
                    "endpoint_type": "local",
                    "endpoint_user": "root",
                    "pre_run": ["ssh_key_setup"],
                    "run_file_format": "yaml_scenario",
                    "results_dir_pattern": "/tmp/results_*",
                },
            },
        },
        runfile_template=RunfileTemplate(
            benchmark="fio", template={"harness": "crucible"}
        ),
    )


@pytest.fixture
def handlers(mock_provider):
    async def noop_clarification(q):
        pass

    h, ssh = create_benchmark_tool_handlers(
        skill_provider=mock_provider,
        request_clarification_fn=noop_clarification,
    )
    return h


@pytest.mark.asyncio
async def test_get_execution_config_crucible(handlers):
    result = await handlers["get_execution_config"](harness_name="crucible")
    assert result["found"] is True
    assert result["harness"] == "crucible"
    assert result["run_command"] == "crucible run"
    assert result["run_file_format"] == "json"
    assert result["default_userenv"] == "alma8"


@pytest.mark.asyncio
async def test_get_execution_config_zathras(handlers):
    result = await handlers["get_execution_config"](harness_name="zathras")
    assert result["found"] is True
    assert result["harness"] == "zathras"
    assert result["run_command"] == "/opt/zathras/bin/burden"
    assert result["run_file_format"] == "yaml_scenario"


@pytest.mark.asyncio
async def test_get_execution_config_not_found(handlers):
    result = await handlers["get_execution_config"](harness_name="unknown_harness")
    assert result["found"] is False


@pytest.mark.asyncio
async def test_no_generate_run_file_tool(handlers):
    assert "generate_run_file" not in handlers


@pytest.mark.asyncio
async def test_no_validate_run_file_tool(handlers):
    assert "validate_run_file" not in handlers
