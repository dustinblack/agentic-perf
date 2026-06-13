# Crucible Run-File Construction — Learned Pitfalls

These are common mistakes when constructing crucible run files,
discovered through real benchmark runs and user feedback.

## Engine ID pairing for client-server benchmarks

For benchmarks with client and server roles (uperf, iperf,
trafficgen), the client and server engines must share the
same ID. The benchmark `ids` field should reference that
single ID.

Correct:
```json
"remotes": [
  {"engines": [{"role": "client", "ids": ["1"]}], "config": {"host": "..."}},
  {"engines": [{"role": "server", "ids": ["1"]}], "config": {"host": "..."}}
]
"benchmarks": [{"name": "uperf", "ids": "1", ...}]
```

Wrong:
```json
"remotes": [
  {"engines": [{"role": "client", "ids": ["1"]}], "config": {"host": "..."}},
  {"engines": [{"role": "server", "ids": ["2"]}], "config": {"host": "..."}}
]
"benchmarks": [{"name": "uperf", "ids": "1-2", ...}]
```

The matching ID creates a paired client-server unit. Multiple
pairs use incrementing IDs (pair 1 gets id "1", pair 2 gets
id "2", etc.).

## Always include tool-params

Even when the docs say tool-params is optional, always include
at least a basic set. An empty or missing tool-params section
can cause crucible to write an empty JSON file that fails to
parse on read-back.

Minimum:
```json
"tool-params": [
  {"tool": "sysstat"},
  {"tool": "procstat"}
]
```

## mv-params is mandatory

Every benchmark object in the `benchmarks` array MUST include
an `mv-params` key — the schema requires it. This is where you
define what the benchmark actually does (test type, message sizes,
duration, etc.).

Use `get_benchmark_params` to discover valid parameters and
presets for each benchmark. At minimum:

```json
"benchmarks": [
  {
    "name": "uperf",
    "ids": "1",
    "mv-params": {
      "sets": [
        {
          "params": [
            {"arg": "test-type", "vals": ["stream"], "role": "client"},
            {"arg": "protocol", "vals": ["tcp"], "role": "client"},
            {"arg": "wsize", "vals": ["16384"], "role": "client"},
            {"arg": "duration", "vals": ["60"], "role": "client"},
            {"arg": "nthreads", "vals": ["1"], "role": "client"},
            {"arg": "remotehost", "vals": ["server-host"], "role": "client"}
          ]
        }
      ]
    }
  }
]
```

For benchmarks with global-options, you can define named param
groups and reference them from sets via `include`:

```json
"mv-params": {
  "global-options": [
    {"name": "common", "params": [...]}
  ],
  "sets": [
    {"include": "common", "params": [...additional per-set...]}
  ]
}
```

## "Use IPs not hostnames" scope

The pitfall about using IP addresses instead of hostnames
applies specifically to the endpoint `host` field in the
`remotes` config section. This is because SSH to hostnames
can trigger IPv6 link-local resolution, causing timeouts.

This rule does NOT apply to benchmark parameters like
`remotehost` in mv-params — hostnames work fine there because
the benchmark itself resolves them within the container.
