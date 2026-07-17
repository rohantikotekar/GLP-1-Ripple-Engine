#!/usr/bin/env bash
# One-command build + push of both images, then print the Akash deploy steps.
#
# Usage:
#   docker login                       # log into your registry first (once)
#   REGISTRY=docker.io/<your-user> ./infra/deploy.sh
#
# REGISTRY examples: docker.io/rajashreeshan  |  ghcr.io/rajashree-shan
set -euo pipefail

REGISTRY="${REGISTRY:?set REGISTRY, e.g. REGISTRY=docker.io/<your-user>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOOP_IMG="$REGISTRY/glp1-ripple-engine:latest"
GUARD_IMG="$REGISTRY/glp1-guardrail:latest"

echo "==> building loop image      $LOOP_IMG"
docker build -f infra/Dockerfile           -t "$LOOP_IMG"  .
echo "==> building guardrail image $GUARD_IMG"
docker build -f infra/guardrail/Dockerfile -t "$GUARD_IMG" .

echo "==> pushing images"
docker push "$LOOP_IMG"
docker push "$GUARD_IMG"

echo "==> stamping REGISTRY into a deploy copy of the SDL"
sed "s#<REGISTRY>#$REGISTRY#g" infra/akash-deploy.yaml > infra/akash-deploy.generated.yaml
echo "    wrote infra/akash-deploy.generated.yaml"

cat <<EOF

==> Images are live. Deploy on Akash one of two ways:

  A) Akash Console (easiest — no CLI):
     1. https://console.akash.network  ->  Deploy  ->  Upload SDL
     2. upload infra/akash-deploy.generated.yaml
     3. pick a provider bid, accept, wait for lease
     4. copy the "URI" it gives you for port 80 -> that's the public loop URL

  B) provider-services CLI (funded wallet required):
     provider-services tx deployment create infra/akash-deploy.generated.yaml --from <key>
     provider-services query market lease list --owner <addr>
     provider-services provider lease-status ... # -> forwarded URL for port 80

Hand the public URL to P1 (loop) and P4 (UI polls it).
EOF
