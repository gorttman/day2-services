# workload-affinity - soft node placement for apps

Convention (documented in day1-foundation's README): each app that wants a
"preferred home" gets a node label `workload-affinity/<app>=primary` on
that node, and optionally `workload-affinity/<app>=secondary` on a backup
node. Labels are managed declaratively by
`day1-foundation/ansible/label-nodes.yml` - **never by hand** - so moving
an app to a new Pi is a one-line change there. App manifests only ever
reference the label *key*, never a hostname.

## Wiring an app in

1. Copy [`affinity-patch.template.yml`](affinity-patch.template.yml) into
   the app's directory as `affinity-patch.yml`.
2. Replace both `APPNAME` occurrences with the app name (must match the
   label key applied by the playbook, e.g. `paperless`).
3. Register it in the app's `kustomization.yml`:

   ```yaml
   patches:
     - path: affinity-patch.yml
       target:
         kind: Deployment        # or StatefulSet
         name: paperless
   ```

The result is a `preferredDuringSchedulingIgnoredDuringExecution` node
affinity: weight 100 toward the app's `primary` node, weight 50 toward a
`secondary` if one is ever labeled. The `secondary` term is harmless while
no node carries that value - it simply never matches.

**Never** change this to `requiredDuringScheduling`: the whole point is
that pods still schedule somewhere when the preferred node is unavailable.

## Status

No app references this yet (as of 2026-07-05). Immich/Paperless run on the
only applications node so the preference would be a no-op, and Nextcloud
is not deployed. Wire it in when a second applications node joins or when
those apps are (re)built.
