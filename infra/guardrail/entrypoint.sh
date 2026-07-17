#!/bin/sh
# Single-container deploy: run the egress guardrail INSIDE the loop container,
# and route the loop's outbound traffic through it. This fits Akash Console's
# single-service flow while keeping the guardrail live in production.
set -e

# 1. start the guardrail proxy on loopback, in the background
GUARDRAIL_PORT=3128 ALLOWLIST_PATH=/etc/guardrail/allowlist.txt python /app/proxy.py &

# 2. wait until it's accepting connections
for _ in $(seq 1 20); do
  if python -c "import socket;socket.create_connection(('127.0.0.1',3128),1).close()" 2>/dev/null; then
    break
  fi
  sleep 0.5
done

# 3. force every outbound call the loop makes through the guardrail.
#    NO_PROXY keeps loopback + the server's own binding direct.
export HTTP_PROXY=http://127.0.0.1:3128  HTTPS_PROXY=http://127.0.0.1:3128
export http_proxy=http://127.0.0.1:3128  https_proxy=http://127.0.0.1:3128
export NO_PROXY=localhost,127.0.0.1      no_proxy=localhost,127.0.0.1

# 4. hand off to the loop server (PID 1 replacement)
exec uvicorn loop.server:app --host 0.0.0.0 --port 8000
