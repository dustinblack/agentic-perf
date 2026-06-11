# End-to-End Testing Guide

How to run an E2E test of the agentic-perf pipeline with Claude acting as both the orchestrating LLM agents and the test operator.

## Prerequisites

1. **Crucible installed locally** at `/opt/crucible` (needed by `CrucibleSkillProvider` to read schemas, multiplex.json, and example run-files)
2. **SSH access** from this machine to both controller and endpoint hosts using the key in `~/.agentic-perf/config.json`
3. **Config file** at `~/.agentic-perf/config.json` with LLM backend settings (see below)
4. **gcloud auth** active if using Vertex backend (`gcloud auth application-default login`)
5. **Secrets deployed** at `~/.agentic-perf/secrets/` (crucible registry tokens — needed by the provisioning agent to install crucible on the controller)

Crucible does NOT need to be pre-installed on the controller host. The provisioning agent installs it automatically during the `awaiting_provision` stage using the install contract in `~/.agentic-perf/private-skills/crucible.json`. If you skip provisioning (see "Skipping Early Stages" below), then crucible must already be on the controller.

### Config file (`~/.agentic-perf/config.json`)

```json
{
    "llm": {
        "provider": "claude",
        "backend": "vertex",
        "project_id": "itpc-gcp-pnd-pe-eng-claude",
        "region": "global",
        "model": "claude-sonnet-4-6"
    },
    "crucible_home": "/opt/crucible",
    "state_store": {
        "url": "http://localhost:8090",
        "port": 8090
    },
    "poll_interval": 3.0,
    "ssh_key": "~/.ssh/id_ed25519_quads"
}
```

## Quick Start

### 1. Start the system

```bash
cd ~/swdev/agentic-perf
./start.sh
```

This launches the state store (background, port 8090) and orchestrator (foreground). Ctrl+C stops both.

### 2. Submit a test ticket (from another terminal)

For a fast E2E test, use a narrow fio request — it runs quickly and validates the full pipeline:

```bash
cd ~/swdev/agentic-perf

python3 cli.py submit \
  "I need to know the performance of ioengine=sync on 4k block size on nfv-amd-5" \
  -d "Controller: nfv-amd-1.perf.eng.bos2.dc.redhat.com (10.26.9.99). Endpoint: nfv-amd-5.perf.eng.bos2.dc.redhat.com (10.26.9.10). SSH key: ~/.ssh/id_ed25519_quads. Use crucible."
```

This creates a ticket in `triage_pending` and goes through the full pipeline: triage → resource → provisioning → benchmark → review.

### 3. Watch progress

```bash
python3 cli.py watch <TICKET_ID> -f -v
```

- `-f` keeps watching after HITL pauses
- `-v` shows agent events (tool calls, LLM interactions)

### 4. Respond to HITL prompts

When the benchmark agent presents a run-file for approval:

```bash
python3 cli.py reply <TICKET_ID> "Approved"
```

## Skipping Early Stages

To test just the benchmark agent (skip triage/resource/provisioning), create a ticket with pre-populated fields and walk it to `executing_benchmark`:

```python
import httpx

client = httpx.Client(base_url='http://localhost:8090', timeout=10.0)

# Create ticket
r = client.post('/api/v1/tickets', json={
    'summary': 'Run fio sync 4k on nfv-amd-5',
    'description': 'Test fio with ioengine=sync, bs=4k on nfv-amd-5 (10.26.9.10). Controller: nfv-amd-1 (10.26.9.99).',
})
tid = r.json()['id']

# Set fields that earlier agents would have populated
client.patch(f'/api/v1/tickets/{tid}/fields', json={
    'fields': {
        'parsed_specs': {
            'controller': '10.26.9.99',
            'sut': '10.26.9.10',
            'harness': 'crucible',
            'benchmark': 'fio',
        },
        'benchmark_suite': 'fio',
        'assigned_hardware_ips': {
            'controller': '10.26.9.99',
            'targets': ['10.26.9.10'],
        },
        'ssh_user': 'root',
        'ssh_key_path': '~/.ssh/id_ed25519_quads',
        'directives': {
            'harness': 'crucible',
            'user_pre_run_approval': True,
        },
    },
})

# Walk through required state transitions
for status in ['triage_pending', 'awaiting_hardware', 'awaiting_provision', 'executing_benchmark']:
    client.post(f'/api/v1/tickets/{tid}/transition', json={
        'status': status,
        'comment': f'Fast-forward for E2E test',
    })

print(f'Ticket {tid} ready in executing_benchmark')
```

## What to Look For

### Success indicators

1. **LLM-driven run-file construction** — orchestrator log shows:
   ```
   Using LLM-constructed run-file (no generate_run_file stash)
   ```
   This confirms the agent used `get_benchmark_params` + `get_example_runfile` to build the run-file directly, not the `generate_run_file` fallback.

2. **Schema validation passed** — no "rejected" status from `execute_benchmark`

3. **Crucible accepted the run-file** — log shows `crucible run <path>` executing without immediate error

4. **Run-file matches the request** — check the run-file in the ticket comments. For a "4k sync" request, `mv-params` should have `"bs": ["4K"]` and `"ioengine": ["sync"]`, not the full matrix from the example.

5. **Ticket reaches `awaiting_review`** — benchmark completed successfully

### Common failures

- **SSH key injection** — if controller → endpoint SSH fails, check that the `agentic-perf-controller-key` in the endpoint's `authorized_keys` matches the controller's `/root/.ssh/id_rsa.pub`
- **Blockbreaker rejection** — invalid run-file structure. Check the error message for which key or value is wrong.
- **HITL re-dispatch** — after user approves and ticket returns to `executing_benchmark`, the orchestrator won't re-pick it up (the `was_dispatched` guard remembers). Restart the orchestrator to clear this state.
- **Vertex auth** — if LLM calls fail, run `gcloud auth application-default login` to refresh credentials

## Cancelling a Running Test

Currently manual:

```bash
ssh -i ~/.ssh/id_ed25519_quads root@<controller> "crucible stop all"
```

Then stop the orchestrator (Ctrl+C or kill the process).

## Unit Tests

Run the unit test suite (no SSH or LLM required):

```bash
cd ~/swdev/agentic-perf
python3 -m pytest tests/ -v
```
