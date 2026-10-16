# Loki + Fluent Bit - cluster logging

Logs from every container and every node's systemd journal, kept long-term and
searched in Grafana (Explore -> Loki). OpenSearch was rejected as too heavy for
the Pi cluster.

    Fluent Bit (DaemonSet, every node)  ->  Loki (1 pod, Longhorn volume for WAL)
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
- **Labels** (low cardinality only): `cluster` (pilab), `node`, `namespace`,
  `app`, `signal_type` (`container` or `host`). Pod name, container name and
  the rest stay in the JSON log line - use `| json` in LogQL.
- **Retention**: compactor on. Default 43800h (5 years); streams with
  `signal_type="host"` (journald) or `"auth"` 87600h (10 years). Change it in
  `loki-values.yml` -> `limits_config`.
- **Outage behaviour**: if Garage or the QNAP is away, Loki keeps accepting logs
  and holds them in the WAL on its Longhorn volume; recent logs stay queryable
  from there.
- **No new exposure**: everything is ClusterIP. Grafana is reached as before.
- **Images** are pinned by digest. They are not mirrored to ghcr.io/gorttman:
  there is no registry push credential on this host. Other upstream images
  (immich, paperless) are pulled directly the same way.
- **Not done**: syslog-ng (only needed if a non-Kubernetes device must send
  syslog); the Telegraf tag taxonomy has no `cluster` / `signal_type` tags yet,
  so the label names here are the starting point for it.

## Files

- `loki-app.yml`, `loki-values.yml` - Loki chart.
- `manifests/` - Garage: config, StatefulSet, Services, setup Job, sealed secret.
- `../fluent-bit/` - the collector.
- Grafana datasource (`loki-pilab`) and dashboard: day1-foundation `apps/grafana`.

## Checks

- `kubectl -n fluent-bit get pods -o wide` - one per node.
- Grafana -> Explore -> Loki -> `{signal_type="host", node="pinode-01"}`.
- `kubectl -n loki logs deploy/...` is a StatefulSet: `kubectl -n loki logs loki-0`
  should show the compactor with retention enabled.
