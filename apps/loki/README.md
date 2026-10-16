# Loki + Alloy - cluster logging

Logs from every container and every node's systemd journal, kept long-term and
searched in Grafana (Explore -> Loki). OpenSearch was rejected as too heavy for
the Pi cluster.

    Alloy (DaemonSet, every node)       ->  Loki (1 pod, Longhorn volume for WAL)
                                                |  chunks + index
                                          Garage (S3) -> QNAP /cold export
    Grafana queries Loki only, never the QNAP.

## Decisions

- **Loki** single-binary, one replica, Helm chart `grafana/loki` 7.3.0 (Loki
  3.6.12). TSDB index, schema v13. Chunks and index in S3, not on NFS.
- **Local volume**: Longhorn, 20 GiB, holds only the write-ahead log, index
  cache and compactor scratch. Losing it costs minutes of recent logs.
- **S3 backend**: Garage v2.3.0 (small, one binary, arm64) as a pod in k3s -
  the QNAP cannot run it. Its block data is on the QNAP `/cold` export (empty
  and unused before this); its metadata database is on a Longhorn volume
  (LMDB must not live on NFS). MinIO and SeaweedFS were the alternatives; Garage
  needs the least memory and no licence question.
- **S3 name**: Loki talks to `s3.loki.svc.cluster.local`, an ExternalName
  Service that points at Garage. To move the store (say, to a NAS-hosted S3),
  repoint that one Service. No Pi-hole record was added: nothing outside the
  cluster talks to it.
- **Credentials**: `garage-secrets` SealedSecret (RPC secret, admin token, S3
  key pair). The key pair is created in the SealedSecret and imported into
  Garage by the `garage-init` Job, so nothing is generated at runtime.
- **Collector: Grafana Alloy, not Fluent Bit.** The spec named Fluent Bit and
  it was tried first: it crash-loops on every node (`jemalloc: Unsupported
  system page size`) because the Pi 5 kernel uses 16 KiB memory pages and its
  allocator supports only 4 KiB. Alloy is Go, has no such limit, and is
  Grafana's own Loki collector. Reads container logs and each node's systemd
  journal. Config in `../alloy/alloy-values.yml`.
- **Labels** (low cardinality only): `cluster` (pilab), `node`, `namespace`,
  `app`, `signal_type` (`container` or `host`). Pod and container name (and the
  systemd unit for host logs) are structured metadata: filter with
  `{app="x"} | pod="x-123"`, they are not labels.
- **Retention**: compactor on. Default 43800h (5 years); streams with
  `signal_type="host"` (journald) or `"auth"` 87600h (10 years). Change it in
  `loki-values.yml` -> `limits_config`.
- **Outage behaviour**: if Garage or the QNAP is away, Loki keeps accepting logs
  and holds them in the WAL on its Longhorn volume; recent logs stay queryable
  from there.
- **No new exposure**: everything is ClusterIP. Grafana is reached as before.
- **Images** (Loki, Alloy, Garage) are mirrored to ghcr.io/gorttman by
  `.github/workflows/mirror-upstream-images.yml` and pinned by digest. The
  mirror is a copy, not a build. The Garage setup Job still uses
  `python:3.12-alpine` from Docker Hub, like the reports app.
- **Not done**: syslog-ng (only needed if a non-Kubernetes device must send
  syslog); the Telegraf tag taxonomy has no `cluster` / `signal_type` tags yet,
  so the label names here are the starting point for it.

## Files

- `loki-app.yml`, `loki-values.yml` - Loki chart.
- `../garage/` - Garage: config, StatefulSet, Services, setup Job, sealed secret.
- `../alloy/` - the collector.
- Grafana datasource (`loki-pilab`) and dashboard: day1-foundation `apps/grafana`.

## Checks

- `kubectl -n alloy get pods -o wide` - one per node.
- Grafana -> Explore -> Loki -> `{signal_type="host", node="pinode-01"}`.
- `kubectl -n loki logs loki-0` should show the compactor with retention enabled.
