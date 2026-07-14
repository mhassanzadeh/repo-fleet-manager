# Runtime health, readiness and ordered startup

RFM distinguishes between a container that is merely running and a service that is ready to accept work. Runtime checks combine Compose container state, Compose health status and optional HTTP, TCP or command probes.

## Commands

```bash
rfm runtime --config repo-fleet.json status
rfm runtime --config repo-fleet.json doctor --logs
rfm runtime --config repo-fleet.json wait --timeout 180 --interval 2
rfm runtime --config repo-fleet.json up --apply
```

- `status` performs one inspection and exits with code `2` when a required service is not ready.
- `doctor` adds reasons, remediation and optional recent logs.
- `wait` polls until all required services are ready or the timeout expires.
- `up` starts dependency levels in order and waits for each level before continuing. It is dry-run unless `--apply` is supplied.

## Configuration

```json
{
  "runtime": {
    "timeout_seconds": 120,
    "interval_seconds": 2,
    "log_tail": 80,
    "default_running_is_ready": true,
    "services": {
      "database": {
        "required": true,
        "depends_on": [],
        "timeout_seconds": 90,
        "probe": {
          "type": "tcp",
          "host": "127.0.0.1",
          "port": 5432,
          "timeout_seconds": 3
        },
        "remediation": "Check database volume permissions and credentials."
      },
      "api": {
        "required": true,
        "depends_on": ["database"],
        "probe": {
          "type": "http",
          "url": "http://127.0.0.1:8080/healthz",
          "method": "GET",
          "expected_status": [200, 204],
          "timeout_seconds": 3
        }
      },
      "worker": {
        "required": false,
        "depends_on": ["database"],
        "probe": {
          "type": "command",
          "command": ["python3", "scripts/worker_probe.py"]
        }
      }
    }
  }
}
```

`runtime` is optional and does not change the config schema version. Profile overlays may override the complete runtime section or individual service values.

## Probe resolution order

For each service RFM evaluates readiness in this order:

1. Explicit `runtime.services.<service>.probe`.
2. Repository `health_url`, converted to an HTTP probe.
3. Repository `host_port`, converted to a TCP probe.
4. Compose container health status.
5. Running-container fallback when `default_running_is_ready` is `true`.

The status output always includes separate `running` and `ready` values even when the running fallback is used.

## Dependency ordering

Dependencies are resolved in this order:

1. Explicit `runtime.services.<service>.depends_on`.
2. Dependencies returned by `compose config --format json`.
3. Repository `depends_on`, mapped through `compose_service`.

Selecting one service with `--service` automatically includes its runtime dependencies. Dependency cycles are rejected during strict config validation when all involved services are explicitly declared.

## Failure diagnostics

```bash
rfm runtime doctor --service api --logs --tail 120
```

A failed report includes:

- container ID and state;
- health state and probe source;
- probe latency and response detail;
- dependency list;
- recent Compose logs when requested;
- configured or generated remediation text.

Machine-readable output is available for CI:

```bash
rfm runtime status --json
rfm runtime doctor --logs --json
rfm runtime wait --timeout 120 --json
```

## Make targets

```bash
make runtime-status CONFIG=repo-fleet.json ROOT=.
make runtime-doctor CONFIG=repo-fleet.json ROOT=. RUNTIME_SERVICE=api
make runtime-wait CONFIG=repo-fleet.json ROOT=. RUNTIME_TIMEOUT=180
make runtime-up CONFIG=repo-fleet.json ROOT=.
make runtime-up-apply CONFIG=repo-fleet.json ROOT=.
```
