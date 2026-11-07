#!/usr/bin/env bash
# Verifies the renderer egress lock in a deployed project (docs/INFRA.md, Renderer egress lock).
#
#   infra/scripts/check-renderer-egress.sh <project-id> [region]
#
# 1. Configuration: the renderer service uses Direct VPC egress with all traffic routed into a
#    subnet, and that subnet's network (read from the service's network-interfaces annotation, so
#    renamed networks are followed) has no router (so no Cloud NAT) and no default route.
# 2. Behaviour: a throwaway Cloud Run job with the renderer's image, service account and network
#    settings tries to open TCP connections to public addresses. Every attempt must fail. The job
#    is deleted afterwards.
#
# Needs gcloud and jq, and a caller that can read Cloud Run and Compute and create jobs (the
# deployer). Exits non-zero when the renderer could reach the internet, or when a check could not
# run: an unclear result is treated as a failure.

set -euo pipefail

project="${1:?usage: check-renderer-egress.sh <project-id> [region]}"
region="${2:-europe-west1}"
job="egress-probe"

fail() {
  echo "FAILED: $*" >&2
  exit 1
}

echo "Checking the renderer service configuration in $project"
service="$(gcloud run services describe renderer --project "$project" --region "$region" --format=json)"
annotations='.spec.template.metadata.annotations'
egress="$(echo "$service" | jq -r "$annotations"'["run.googleapis.com/vpc-access-egress"] // ""')"
[ "$egress" = "all-traffic" ] || fail "the renderer's VPC egress is '${egress:-none}', not all-traffic"

# The annotation lists the network and subnet by name or by full path; keep the last segment.
interfaces="$(echo "$service" | jq -r "$annotations"'["run.googleapis.com/network-interfaces"] // "[]"')"
network="$(echo "$interfaces" | jq -r '.[0].network // "" | split("/") | last // ""')"
subnet="$(echo "$interfaces" | jq -r '.[0].subnetwork // "" | split("/") | last // ""')"
[ -n "$network" ] && [ -n "$subnet" ] || fail "the renderer has no network and subnet for Direct VPC egress"
echo "ok: the renderer routes all traffic into subnet $subnet of network $network"

routers="$(gcloud compute routers list --project "$project" \
  --filter="network~/${network}\$" --format='value(name)')"
[ -z "$routers" ] || fail "$network has a router ($routers); remove it and any Cloud NAT on it"
echo "ok: $network has no router, so no Cloud NAT"

default_routes="$(gcloud compute routes list --project "$project" \
  --filter="network~/${network}\$ AND destRange=0.0.0.0/0" --format='value(name)')"
[ -z "$default_routes" ] || fail "$network has a default route ($default_routes)"
echo "ok: $network has no default route"

echo "Probing from a job with the renderer's image and network settings"
image="$(echo "$service" | jq -r '.spec.template.spec.containers[0].image')"
service_account="$(echo "$service" | jq -r '.spec.template.spec.serviceAccountName')"
[ -n "$image" ] && [ "$image" != "null" ] || fail "could not read the renderer image"
[ -n "$service_account" ] && [ "$service_account" != "null" ] || fail "could not read the renderer service account"

cleanup() {
  gcloud run jobs delete "$job" --project "$project" --region "$region" --quiet >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Exit code 1 means a connection succeeded. The code has commas, so gcloud's custom list
# delimiter (^@^) is used for --args.
probe='import socket, sys
for host in ("1.1.1.1", "8.8.8.8"):
    try:
        socket.create_connection((host, 443), timeout=8).close()
    except OSError as error:
        print("blocked:", host, type(error).__name__)
    else:
        print("REACHED:", host)
        sys.exit(1)
'

gcloud run jobs deploy "$job" --project "$project" --region "$region" \
  --image "$image" --service-account "$service_account" \
  --network "$network" --subnet "$subnet" --vpc-egress all-traffic \
  --max-retries 0 --task-timeout 120s \
  --command python --args="^@^-c@${probe}" >/dev/null

if gcloud run jobs execute "$job" --project "$project" --region "$region" --wait >/dev/null; then
  echo "ok: no outbound connection succeeded from the renderer's network"
else
  fail "the probe job failed: either it reached the internet or it could not run; see its logs: gcloud logging read 'resource.labels.job_name=\"$job\"' --project $project --limit 20"
fi
