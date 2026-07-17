# Egress guardrail — tiny stdlib-only forward proxy. No pip deps.
FROM python:3.11-slim
WORKDIR /app
COPY infra/guardrail/proxy.py .
COPY infra/guardrail/allowlist.txt /etc/guardrail/allowlist.txt
ENV GUARDRAIL_PORT=3128 ALLOWLIST_PATH=/etc/guardrail/allowlist.txt
EXPOSE 3128
CMD ["python", "proxy.py"]
