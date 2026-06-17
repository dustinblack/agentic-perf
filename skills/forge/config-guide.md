# Forge Config Construction Guide

Forge (PSAP) runs LLM inference benchmarks on K8s GPU clusters.
The run-file specifies a project, presets, and CLI args.

## Run-File Format

```json
{
  "harness": "forge",
  "project": "rhaiis",
  "presets": ["llama-3-1-8b", "profile1", "nvidia"],
  "cli_args": ["--max-seconds", "300", "--rates", "1,50,100"],
  "config_overrides": {}
}
```

## Projects

### rhaiis (recommended for PSAP CC clusters)
Deploys vLLM on KServe InferenceService, benchmarks with GuideLLM.
Requires KServe + GPU operator pre-installed on cluster.
Minimal `prepare` phase — just creates namespace.

### llm_d (for bare OpenShift clusters)
Deploys LLMInferenceService with EPP scheduler.
Full `prepare` phase installs GPU operator, NFD, cert-manager,
RHOAI, KServe, downloads model. Requires OpenShift >= 4.19.9.

## Preset Stacking

Presets are applied left to right. Compose model + workload + accelerator:

```
--preset llama-3-3-70b-fp8 --preset profile2 --preset nvidia
```

### Preset categories:
- **Model**: llama-3-1-8b, llama-3-3-70b-fp8, qwen3-0_6b, etc.
- **Workload** (rhaiis): profile1, profile2, profile3, profile4
- **Accelerator**: nvidia, amd
- **Scheduler** (llm_d): approximate, precise, approximate-prefix-cache
- **Benchmark** (llm_d): smoke, benchmark-short, cks

## CLI Args (test phase)

| Arg | Description |
|-----|-------------|
| `--rates` | Comma-separated request rates (req/s) |
| `--max-seconds` | Duration per rate point (seconds) |
| `--tensor-parallel` / `-tp` | GPU count override |
| `--replicas` / `-r` | Serving replica count |
| `--model` / `-m` | Model key override |
| `--namespace` / `-n` | K8s namespace |
| `--vllm-image` | Custom vLLM container image |
| `--dry-run` | Print plan without executing |

## Execution Lifecycle

```
forge prepare  → creates namespace, verifies access (rhaiis)
                 OR installs full stack (llm_d)
forge test     → deploys model, runs GuideLLM benchmark, captures results
forge cleanup  → removes InferenceService (implicit in test)
```

## Results

Forge produces artifacts in ARTIFACT_DIR:
- `ai_eval_payload.json` — agent-friendly summary with headline metrics
- `kpis.jsonl` — 12 KPIs per test config (JSONL, one record per line)
- HTML reports with Plotly charts

Key KPIs (from GuideLLM):
- `guidellm_tokens_per_second` (higher is better)
- `guidellm_ttft_p95` — time to first token (lower is better)
- `guidellm_request_latency_p95` (lower is better)
- `guidellm_request_rate` (higher is better)

## Config Overrides

Dot-separated config paths override base config:

```json
{
  "config_overrides": {
    "tests.rhaiis.vllm_image": "custom-image:latest",
    "tests.rhaiis.tensor_parallel_size": "4"
  }
}
```
