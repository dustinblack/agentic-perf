# Crucible Userenv Selection Guide

A userenv (user environment) determines the base container
image used to run benchmark and tool engines. Each userenv
is a specific OS distribution and version.

## Valid userenv names

Userenvs are defined in rickshaw's `userenvs/` directory.
Each has a `<name>.json` config file. Common valid names:

- `fedora-latest` — latest Fedora (recommended default)
- `fedora42`, `fedora43` — specific Fedora versions
- `rhubi8`, `rhubi9`, `rhubi10` — RHEL UBI images
- `alma8`, `alma9`, `alma10` — AlmaLinux
- `stream8`, `stream9`, `stream10` — CentOS Stream

Use `crucible userenvs list` to see the full list on a
given installation.

## "default" is NOT a valid userenv

Workshop.json files for benchmarks and tools contain a
`"name": "default"` entry in their `userenvs` array. This
is a FALLBACK CATEGORY — it defines the dependency
requirements for any userenv not explicitly listed. It is
NOT a literal userenv name you can use in a run file.

Setting `"userenv": "default"` in a run file will fail
because there is no `userenvs/default.json` file in
rickshaw.

## How to choose a userenv

1. Use `fedora-latest` as a safe default for most benchmarks
2. For trafficgen (TRex/testpmd), use `alma8` — TRex
   packages are only built for this userenv
3. For RHEL-specific testing, use `rhubi8`, `rhubi9`, or
   `rhubi10`
4. All tools (sysstat, procstat, etc.) use their own
   userenv independently — typically `fedora-latest`

## How userenvs work internally

1. Each benchmark and tool has a `workshop.json` declaring
   requirements per userenv (packages, source builds)
2. Rickshaw combines all workshop.json files into a merged
   config for the requested userenv
3. The image-sourcing service builds or finds a container
   image tagged with a hash of the combined requirements
4. If the userenv name doesn't match any `<name>.json` file
   in rickshaw's userenvs directory, the build fails before
   the image hash can even be computed
