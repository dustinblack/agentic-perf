# Next Session Notes

## LLM-Driven Run-File Generation (Priority: High)

Redesign the benchmark agent to construct run.json directly from natural language instead of going through the `generate_run_file` template layer. Full design doc: [design-llm-runfile-generation.md](design-llm-runfile-generation.md).

## ~~Triage Directives~~ (Done)

Implemented: `directives` field in triage submit schema with `on_existing_install`,
`harness`, `user_pre_run_approval`, `host_cleanup`, plus arbitrary keys for extensibility.
Provisioning and benchmark agents check directives before falling back to skill config defaults.
Benchmark agent now asks for user approval before executing (unless `user_pre_run_approval: false`).

## Remote Skills Loading (Priority: Medium)

Currently CrucibleSkillProvider and ZathrasSkillProvider need local repo clones. The architecture should be:
- **Before install**: lightweight benchmark catalog in private skill config (names, roles, min_hosts)
- **After install**: benchmark agent loads detailed skills from the controller's harness installation (schemas, example run-files, test_defs.yml)

This decouples the orchestrator machine from needing harness repos locally.

## Checkpoint/Restart on Tickets

Instead of resubmitting from scratch when a phase fails, support rewinding a ticket to a previous state. The ticket has all accumulated context (hardware IPs, SSH key, harness version). A `rewind` CLI command would transition the ticket back and let the dispatcher re-run just the failed phase. Need to define which custom_fields to clear on rewind.

## QUADS Orphaned Assignments

The QUADS terminate API returns 500 for assignments with expired schedules (0 hosts). The teardown agent should:
1. Try to delete host schedules first
2. Then terminate the assignment
3. Catch 500 and log as warning, not failure

Also file QUADS issue — RFE #605 mentions auto-cleanup of orphaned assignments.

## Zathras-Specific Issues

- `bin/install.sh` doesn't install `gh` (GitHub CLI) — needed for version checks
- `--skip_test_version_check` is a workaround; upstream should make version checks optional or not require `gh`
- `dnf config-manager --add-repo` doesn't work on dnf5 (Fedora 41+) — zathras is RHEL-only in practice
- Install script should be more self-contained about its deps
