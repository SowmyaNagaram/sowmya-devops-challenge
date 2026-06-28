# Skybyte DevOps Challenge — Sowmya Nagaram

## What Was Wrong and What Changed

The starter repository had critical defects across security, reliability,
hygiene, and documentation. The container ran as root with no security
context, a production secret was committed in plaintext in three separate
files, the CI pipeline reported green while validating nothing (flake8
excluded every file it should lint, helm lint and terraform validate both
used || true to swallow errors), probes pointed to the wrong endpoint with
no thresholds, the app had no SIGTERM handler and used Flask's dev server
in production, and there were no resource limits. All defects are
documented in AUDIT.md with file paths, impact, and fixes applied.

---

## Prerequisites

Tested with these versions:

| Tool | Version |
|------|---------|
| Docker | 24.x+ |
| Minikube | 1.32.x+ |
| kubectl | 1.28.x+ |
| Helm | 3.14.x+ |
| Terraform | 1.5.x+ |
| Python | 3.11.x+ |

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/SowmyaNagaram/sowmya-devops-challenge.git
cd sowmya-devops-challenge

# Start Minikube
minikube start

# Set the API token (never hardcoded)
export TF_VAR_api_token="your-secret-here"

# Run setup
chmod +x setup.sh
./setup.sh

# Run system checks
chmod +x system-checks.sh
./system-checks.sh
```

---

## SLO Statement

99% of requests to `/` complete in under 250ms over a rolling 7-day
window. We detect a breach by alerting on the
`http_request_duration_seconds` histogram's p99 bucket exceeding 250ms
for 5 consecutive minutes using a Prometheus alerting rule on the
`http_request_duration_seconds_bucket` metric with `le="0.25"` label.

---

## Repository Structure
