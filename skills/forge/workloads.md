# Forge Model Catalog and Workload Profiles

## Workload Profiles (rhaiis)

| Profile | Input Tokens | Output Tokens | Rates (req/s) | Duration | Use Case |
|---------|-------------|---------------|---------------|----------|----------|
| profile1 | 1000 fixed | 1000 fixed | 1,50,100,200,300 | 450s | Balanced throughput |
| profile2 | 512 ±128 | 2048 ±512 | 1,50,100,200,300 | 450s | Variable-length generation |
| profile3 | 2048 fixed | 128 fixed | 1,50,100,200,300 | 450s | Prefill-heavy / summarization |
| profile4 | 8000 fixed | 1000 fixed | 1,25,50,75,100 | 450s | Long-context |

## Model Families

### Llama
| Preset Key | Size | TP | Quantization |
|-----------|------|-----|--------------|
| llama-3-1-8b | 8B | 1 | None |
| llama-3-3-70b | 70B | 4 | None |
| llama-3-3-70b-fp8 | 70B | 4 | FP8 |
| llama-3-3-70b-w8a8 | 70B | 4 | W8A8 |
| llama-3-3-70b-w4a16 | 70B | 4 | W4A16 |
| llama-4-scout | 17B-16E MoE | 4 | None |
| llama-4-scout-fp8 | 17B-16E MoE | 2 | FP8 |
| llama-4-scout-int4 | 17B-16E MoE | 2 | INT4 |
| llama-4-maverick | 17B-128E MoE | 8 | None |
| llama-4-maverick-fp8 | 17B-128E MoE | 8 | FP8 |
| llama-4-maverick-w4a16 | 17B-128E MoE | 8 | W4A16 |

### Mistral
| Preset Key | Size | TP | Quantization |
|-----------|------|-----|--------------|
| mistral-2503 | 24B | 1 | None |
| mistral-2503-fp8 | 24B | 1 | FP8 |
| mistral-2503-w8a8 | 24B | 1 | W8A8 |
| mistral-2503-w4a16 | 24B | 1 | W4A16 |
| mistral-7b | 7B | 1 | None |
| mixtral-8x7b | 8x7B MoE | 1 | None |

### Granite
| Preset Key | Size | TP | Quantization |
|-----------|------|-----|--------------|
| granite-3-1-8b-instruct | 8B | 1 | None |
| granite-3-1-8b-fp8 | 8B | 1 | FP8 |
| granite-3-1-8b-w8a8 | 8B | 1 | W8A8 |
| granite-3-1-8b-w4a16 | 8B | 1 | W4A16 |

### Qwen
| Preset Key | Size | TP | Quantization |
|-----------|------|-----|--------------|
| qwen25-7b-instruct | 7B | 1 | None |
| qwen25-7b-fp8 | 7B | 1 | FP8 |
| qwen3-0_6b | 0.6B | 1 | None (validation model) |
| qwen3-235b-instruct | 235B MoE | 4 | None |
| qwen3-235b-instruct-fp8 | 235B MoE | 4 | FP8 |

### DeepSeek
| Preset Key | Size | TP | Quantization |
|-----------|------|-----|--------------|
| deepseek-r1-0528 | 671B MoE | 8 | None |
| deepseek-r1-0528-w4a16 | 671B MoE | 8 | W4A16 |
| deepseek-v3-2 | 671B MoE | 8 | None |
| deepseek-v4-pro | MoE | 8 | None |

### Nemotron
| Preset Key | Size | TP | Quantization |
|-----------|------|-----|--------------|
| nemotron-3-1-70b | 70B | 2 | None |
| nemotron-3-1-70b-fp8 | 70B | 1 | FP8 |
| nemotron3nano-30b | 30B MoE | 1 | BF16 |

### Gemma
| Preset Key | Size | TP | Quantization |
|-----------|------|-----|--------------|
| gemma-9b | 9B | 1 | None |
| gemma-9b-fp8 | 9B | 1 | FP8 |

### GPT-OSS
| Preset Key | Size | TP | Quantization |
|-----------|------|-----|--------------|
| gpt-oss-120b | 120B | 1 | None |
| gpt-oss-120b-fp8 | 120B | 1 | FP8 |
| gpt-oss-20b | 20B | 1 | None |

## GPU Requirements

TP (Tensor Parallel) = number of GPUs needed per replica.

| TP Size | Example Models | Min Cluster |
|---------|---------------|-------------|
| 1 | 8B models, mistral-24b, qwen-7b | 1 GPU |
| 2 | llama-4-scout-fp8, nemotron-70b | 2 GPUs |
| 4 | 70B models, qwen3-235b, llama-4-scout | 4 GPUs |
| 8 | maverick, deepseek-r1/v3/v4 | 8 GPUs |

## Quantization Guide

| Format | Memory Savings | Quality Impact | When to Use |
|--------|---------------|----------------|-------------|
| None (FP16/BF16) | Baseline | Best quality | When GPU memory allows |
| FP8 | ~50% | Minimal loss | Default for large models |
| W8A8 | ~50% | Small loss | Good throughput/quality balance |
| W4A16 | ~75% | Moderate loss | When GPU memory is tight |

## Quick Start Examples

Small model validation (1 GPU, ~2 min):
```
project: rhaiis, presets: [qwen3-0_6b, profile1, nvidia]
```

Production benchmark (4 GPUs, ~30 min):
```
project: rhaiis, presets: [llama-3-3-70b-fp8, profile1, nvidia]
cli_args: [--max-seconds, 450, --rates, 1,50,100,200,300]
```

Large model on 8 GPUs:
```
project: rhaiis, presets: [llama-4-maverick-fp8, profile1, nvidia]
```
