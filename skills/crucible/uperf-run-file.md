# uperf Run-File Construction Guide

uperf is a client-server network benchmark. The client
generates traffic to the server and measures throughput
and latency.

## Required mv-params

The client must know where the server is. Use one of:

- **`remotehost`** (role: client) — hostname or IP of the
  server host. Use this when you know the server's address.
- **`ifname`** (role: server) — network interface name on
  the server. The server-start script finds the IP from the
  interface and sends it to the client via roadblock. Use
  this when the server has multiple interfaces and you want
  to target a specific one.

For most cases, use `remotehost` with the server's hostname
or IP address.

## Typical uperf mv-params

```json
"mv-params": {
  "sets": [
    {
      "params": [
        {"arg": "test-type", "vals": ["stream"], "role": "client"},
        {"arg": "protocol", "vals": ["tcp"], "role": "client"},
        {"arg": "wsize", "vals": ["16384"], "role": "client"},
        {"arg": "duration", "vals": ["30"], "role": "client"},
        {"arg": "nthreads", "vals": ["1"], "role": "client"},
        {"arg": "remotehost", "vals": ["<server-hostname-or-ip>"], "role": "client"}
      ]
    }
  ]
}
```

## Engine IDs

Client and server must share the same engine ID (see
run-file-pitfalls.md). For a single client-server pair:

```json
"remotes": [
  {
    "engines": [{"role": "client", "ids": ["1"]}],
    "config": {"host": "<client-ip>", "settings": {"userenv": "fedora-latest", "osruntime": "podman"}}
  },
  {
    "engines": [{"role": "server", "ids": ["1"]}],
    "config": {"host": "<server-ip>", "settings": {"userenv": "fedora-latest", "osruntime": "podman"}}
  }
]
```

Benchmark section references the same ID:
```json
"benchmarks": [{"name": "uperf", "ids": "1", "mv-params": {...}}]
```

## Valid parameter values

From multiplex.json:
- **test-type**: stream, crr, rr, ping-pong
- **protocol**: tcp, udp
- **ipv**: 4, 6
- **wsize/rsize/nthreads/duration**: positive integers
- **remotehost**: any hostname or IP
- **ifname**: any network interface name
