from __future__ import annotations

import pytest

from providers.skills.forge import ForgeSkillProvider


@pytest.fixture
def provider() -> ForgeSkillProvider:
    return ForgeSkillProvider()


@pytest.mark.asyncio
async def test_list_benchmarks(provider: ForgeSkillProvider):
    benchmarks = await provider.list_benchmarks()
    names = [b.name for b in benchmarks]
    assert len(benchmarks) == 2
    assert "forge-rhaiis" in names
    assert "forge-llm-d" in names


@pytest.mark.asyncio
async def test_harness_field(provider: ForgeSkillProvider):
    benchmarks = await provider.list_benchmarks()
    for b in benchmarks:
        assert b.harness == "forge"


@pytest.mark.asyncio
async def test_endpoint_types_kube(provider: ForgeSkillProvider):
    benchmarks = await provider.list_benchmarks()
    for b in benchmarks:
        assert "kube" in b.endpoint_types


@pytest.mark.asyncio
async def test_get_benchmark_found(provider: ForgeSkillProvider):
    b = await provider.get_benchmark("forge-rhaiis")
    assert b is not None
    assert b.name == "forge-rhaiis"
    assert b.harness == "forge"


@pytest.mark.asyncio
async def test_get_benchmark_llm_d(provider: ForgeSkillProvider):
    b = await provider.get_benchmark("forge-llm-d")
    assert b is not None
    assert b.name == "forge-llm-d"
    assert b.harness == "forge"


@pytest.mark.asyncio
async def test_get_benchmark_not_found(provider: ForgeSkillProvider):
    b = await provider.get_benchmark("nonexistent")
    assert b is None


@pytest.mark.asyncio
async def test_resolve_benchmark_inference(provider: ForgeSkillProvider):
    result = await provider.resolve_benchmark(
        {"description": "llm inference benchmark"}
    )
    assert result is not None
    assert result.startswith("forge-")


@pytest.mark.asyncio
async def test_resolve_benchmark_rhaiis(provider: ForgeSkillProvider):
    result = await provider.resolve_benchmark(
        {"description": "rhaiis vllm inference test"}
    )
    assert result == "forge-rhaiis"


@pytest.mark.asyncio
async def test_resolve_benchmark_llm_d(provider: ForgeSkillProvider):
    result = await provider.resolve_benchmark(
        {"description": "llm-d distributed inference epp"}
    )
    assert result == "forge-llm-d"


@pytest.mark.asyncio
async def test_resolve_benchmark_model_name(provider: ForgeSkillProvider):
    result = await provider.resolve_benchmark(
        {"description": "benchmark llama inference on gpu"}
    )
    assert result is not None
    assert result.startswith("forge-")


@pytest.mark.asyncio
async def test_resolve_benchmark_gpu_type(provider: ForgeSkillProvider):
    result = await provider.resolve_benchmark(
        {"description": "a100 gpu inference test"}
    )
    assert result is not None
    assert result.startswith("forge-")


@pytest.mark.asyncio
async def test_resolve_benchmark_no_match(provider: ForgeSkillProvider):
    result = await provider.resolve_benchmark(
        {"description": "network throughput netperf iperf"}
    )
    assert result is None


@pytest.mark.asyncio
async def test_generate_runfile_rhaiis_defaults(provider: ForgeSkillProvider):
    result = await provider.generate_runfile("forge-rhaiis", {})
    t = result.template
    assert t["harness"] == "forge"
    assert t["project"] == "rhaiis"
    assert isinstance(t["presets"], list)
    assert "profile1" in t["presets"]
    assert "nvidia" in t["presets"]
    assert isinstance(t["cli_args"], list)


@pytest.mark.asyncio
async def test_generate_runfile_rhaiis_with_model(provider: ForgeSkillProvider):
    result = await provider.generate_runfile(
        "forge-rhaiis",
        {"model": "llama-3-3-70b-fp8", "workload_profile": "profile3"},
    )
    t = result.template
    assert t["project"] == "rhaiis"
    assert "llama-3-3-70b-fp8" in t["presets"]
    assert "profile3" in t["presets"]


@pytest.mark.asyncio
async def test_generate_runfile_rhaiis_with_rates(provider: ForgeSkillProvider):
    result = await provider.generate_runfile(
        "forge-rhaiis",
        {"model": "llama-3-1-8b", "rates": "1,50,100", "max_seconds": 300},
    )
    args = result.template["cli_args"]
    assert "--rates" in args
    assert "1,50,100" in args
    assert "--max-seconds" in args
    assert "300" in args


@pytest.mark.asyncio
async def test_generate_runfile_rhaiis_tensor_parallel(provider: ForgeSkillProvider):
    result = await provider.generate_runfile(
        "forge-rhaiis",
        {"model": "llama-3-3-70b", "tensor_parallel": 4},
    )
    args = result.template["cli_args"]
    assert "--tensor-parallel" in args
    assert "4" in args


@pytest.mark.asyncio
async def test_generate_runfile_rhaiis_replicas(provider: ForgeSkillProvider):
    result = await provider.generate_runfile(
        "forge-rhaiis",
        {"model": "llama-3-1-8b", "replicas": 2},
    )
    args = result.template["cli_args"]
    assert "--replicas" in args
    assert "2" in args


@pytest.mark.asyncio
async def test_generate_runfile_rhaiis_single_replica_omitted(
    provider: ForgeSkillProvider,
):
    result = await provider.generate_runfile(
        "forge-rhaiis",
        {"model": "llama-3-1-8b", "replicas": 1},
    )
    args = result.template["cli_args"]
    assert "--replicas" not in args


@pytest.mark.asyncio
async def test_generate_runfile_llm_d_defaults(provider: ForgeSkillProvider):
    result = await provider.generate_runfile("forge-llm-d", {})
    t = result.template
    assert t["harness"] == "forge"
    assert t["project"] == "llm_d"
    assert "nvidia" in t["presets"]


@pytest.mark.asyncio
async def test_generate_runfile_llm_d_with_scheduler(provider: ForgeSkillProvider):
    result = await provider.generate_runfile(
        "forge-llm-d",
        {"model": "qwen3-0_6b", "scheduler_profile": "precise", "benchmark_key": "short"},
    )
    t = result.template
    assert "qwen3-0_6b" in t["presets"]
    assert "precise" in t["presets"]
    assert "short" in t["presets"]


@pytest.mark.asyncio
async def test_generate_runfile_config_overrides(provider: ForgeSkillProvider):
    result = await provider.generate_runfile(
        "forge-rhaiis",
        {
            "model": "llama-3-1-8b",
            "config_overrides": {"tests.rhaiis.vllm_image": "custom:latest"},
        },
    )
    t = result.template
    assert "config_overrides" in t
    assert t["config_overrides"]["tests.rhaiis.vllm_image"] == "custom:latest"


@pytest.mark.asyncio
async def test_generate_runfile_unknown(provider: ForgeSkillProvider):
    result = await provider.generate_runfile("nonexistent", {})
    assert result.template == {}


@pytest.mark.asyncio
async def test_get_benchmark_params_rhaiis(provider: ForgeSkillProvider):
    params = await provider.get_benchmark_params("forge-rhaiis")
    assert params is not None
    assert "model" in params
    assert "workload_profile" in params
    assert "rates" in params
    assert "accelerator" in params


@pytest.mark.asyncio
async def test_get_benchmark_params_llm_d(provider: ForgeSkillProvider):
    params = await provider.get_benchmark_params("forge-llm-d")
    assert params is not None
    assert "model" in params
    assert "scheduler_profile" in params
    assert "benchmark_key" in params


@pytest.mark.asyncio
async def test_get_benchmark_params_not_found(provider: ForgeSkillProvider):
    params = await provider.get_benchmark_params("nonexistent")
    assert params is None


@pytest.mark.asyncio
async def test_get_runfile_schema(provider: ForgeSkillProvider):
    schema = await provider.get_runfile_schema()
    assert schema is not None
    assert schema["type"] == "object"
    assert "project" in schema["properties"]
    assert "presets" in schema["properties"]
    assert "cli_args" in schema["properties"]


@pytest.mark.asyncio
async def test_get_example_runfile_rhaiis(provider: ForgeSkillProvider):
    example = await provider.get_example_runfile("forge-rhaiis")
    assert example is not None
    assert example["harness"] == "forge"
    assert example["project"] == "rhaiis"
    assert isinstance(example["presets"], list)
    assert len(example["presets"]) > 0


@pytest.mark.asyncio
async def test_get_example_runfile_llm_d(provider: ForgeSkillProvider):
    example = await provider.get_example_runfile("forge-llm-d")
    assert example is not None
    assert example["harness"] == "forge"
    assert example["project"] == "llm_d"


@pytest.mark.asyncio
async def test_get_example_runfile_not_found(provider: ForgeSkillProvider):
    example = await provider.get_example_runfile("nonexistent")
    assert example is None


@pytest.mark.asyncio
async def test_validate_runfile_valid(provider: ForgeSkillProvider):
    result = await provider.generate_runfile(
        "forge-rhaiis", {"model": "llama-3-1-8b"}
    )
    validation = await provider.validate_runfile(result.template)
    assert validation["valid"] is True
    assert validation["errors"] == []


@pytest.mark.asyncio
async def test_validate_runfile_missing_project(provider: ForgeSkillProvider):
    validation = await provider.validate_runfile(
        {"harness": "forge", "presets": ["llama-8b"]}
    )
    assert validation["valid"] is False
    assert any("project" in e.lower() for e in validation["errors"])


@pytest.mark.asyncio
async def test_validate_runfile_invalid_project(provider: ForgeSkillProvider):
    validation = await provider.validate_runfile(
        {"harness": "forge", "project": "bogus", "presets": ["llama-8b"]}
    )
    assert validation["valid"] is False
    assert any("bogus" in e for e in validation["errors"])


@pytest.mark.asyncio
async def test_validate_runfile_missing_presets(provider: ForgeSkillProvider):
    validation = await provider.validate_runfile(
        {"harness": "forge", "project": "rhaiis"}
    )
    assert validation["valid"] is False
    assert any("presets" in e.lower() for e in validation["errors"])


@pytest.mark.asyncio
async def test_validate_runfile_empty_presets(provider: ForgeSkillProvider):
    validation = await provider.validate_runfile(
        {"harness": "forge", "project": "rhaiis", "presets": []}
    )
    assert validation["valid"] is False


@pytest.mark.asyncio
async def test_validate_runfile_bad_cli_args(provider: ForgeSkillProvider):
    validation = await provider.validate_runfile(
        {"harness": "forge", "project": "rhaiis", "presets": ["llama-8b"], "cli_args": "not-a-list"}
    )
    assert validation["valid"] is False
    assert any("cli_args" in e for e in validation["errors"])


@pytest.mark.asyncio
async def test_validate_runfile_bad_config_overrides(provider: ForgeSkillProvider):
    validation = await provider.validate_runfile(
        {"harness": "forge", "project": "rhaiis", "presets": ["llama-8b"], "config_overrides": "bad"}
    )
    assert validation["valid"] is False
    assert any("config_overrides" in e for e in validation["errors"])


@pytest.mark.asyncio
async def test_validate_generated_runfiles_pass(provider: ForgeSkillProvider):
    for benchmark in ("forge-rhaiis", "forge-llm-d"):
        result = await provider.generate_runfile(benchmark, {"model": "llama-3-1-8b"})
        validation = await provider.validate_runfile(result.template)
        assert validation["valid"] is True, f"{benchmark}: {validation['errors']}"


@pytest.mark.asyncio
async def test_get_default_config(provider: ForgeSkillProvider):
    config = await provider.get_default_config()
    assert "provisioning" in config
    assert "execution" in config
    prov = config["provisioning"]
    assert prov["install_method"] == "git_clone"
    assert "forge" in prov["git_url"]
    assert "pip install" in prov["post_install_commands"][0]
    exe = config["execution"]
    assert exe["controller_required"] is True
    assert exe["endpoint_type"] == "kube"
    assert "run_cli" in exe["run_command"]
