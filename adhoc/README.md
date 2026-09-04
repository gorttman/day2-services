# adhoc

Manifests that are real, applied, and must survive a rebuild, but are
deliberately **not** synced by ArgoCD.

Nothing here is under `apps/`, so the day2-services app-of-apps never
sees it. Apply these by hand after a rebuild.

## immich-tagging-sealedsecret.yml

`IMMICH_API_KEY`, sealed for the `default` namespace. Consumed by ad-hoc
Immich photo-tagging Jobs. Kept in `default` rather than re-sealed into
the `immich` namespace because the Jobs that reference it live there.

Apply with:

    kubectl apply -f adhoc/immich-tagging-sealedsecret.yml
