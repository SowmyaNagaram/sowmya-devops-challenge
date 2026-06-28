# Audit Report — Skybyte DevOps Challenge

This document lists every defect found in the starter repository,
categorized by type, with the file path, what was wrong, why it
matters in production, and the fix applied.

---

## Security

### SEC-01: Container runs as root
**File:** `Dockerfile`
**What's wrong:** No `USER` instruction — process runs as UID 0 (root)
**Why it matters:** If the app is compromised, the attacker has root
inside the container and can escape more easily. Violates principle
of least privilege.
**Fix:** Added `groupadd`/`useradd` and `USER appuser` in Dockerfile.

---

### SEC-02: Unpinned base image
**File:** `Dockerfile`
**What's wrong:** `FROM python:3.9` — no digest or slim variant, pulls
whatever is latest for that tag
**Why it matters:** Image contents can change silently between builds,
introducing vulnerabilities. Non-slim image has unnecessary packages
that increase attack surface.
**Fix:** Changed to `FROM python:3.11-slim`

---

### SEC-03: Plaintext secret in values.yaml
**File:** `helm/skybyte-app/values.yaml`
**What's wrong:** `apiToken: "sk-skybyte-prod-7f3c9a2b1e8d4a6c"` —
real production secret committed to git
**Why it matters:** Anyone with repo access has the production token.
Git history means it persists even after deletion.
**Fix:** Removed from values.yaml entirely. Secret is now managed via
Terraform `kubernetes_secret` resource and injected via `secretKeyRef`.

---

### SEC-04: Plaintext secret in terraform variables
**File:** `terraform/variables.tf`
**What's wrong:** `default = "sk-skybyte-prod-7f3c9a2b1e8d4a6c"` —
same secret hardcoded as default value, no `sensitive = true`
**Why it matters:** Terraform will print this value in plan output and
logs. Secret is committed to git.
**Fix:** Removed default value, added `sensitive = true`. Secret must
now be passed via `TF_VAR_api_token` environment variable.

---

### SEC-05: No securityContext on container
**File:** `helm/skybyte-app/templates/deployment.yaml`
**What's wrong:** No `securityContext` block at all — no
`runAsNonRoot`, no `readOnlyRootFilesystem`, no dropped capabilities,
no `allowPrivilegeEscalation: false`
**Why it matters:** Container runs with full Linux capabilities and
writable filesystem. A compromised container can modify its own
binaries and escalate privileges.
**Fix:** Added full `securityContext` at both pod and container level.

---

### SEC-06: Secret passed as plain env var from values
**File:** `helm/skybyte-app/templates/deployment.yaml`
**What's wrong:** `value: {{ .Values.apiToken | quote }}` — secret
flows directly from plaintext values into pod environment variable
**Why it matters:** Secret is visible in `helm get values`, `kubectl
describe pod`, and any tooling that reads values.
**Fix:** Changed to `secretKeyRef` referencing the Kubernetes secret
created by Terraform.

---

### SEC-07: App binds to privileged port 80
**File:** `app/main.py`
**What's wrong:** `app.run(host="0.0.0.0", port=80)` — port 80 is a
privileged port requiring root
**Why it matters:** Non-root user cannot bind to ports below 1024,
so fixing SEC-01 would break the app without also fixing this.
**Fix:** Changed to port 8080 everywhere — app, Dockerfile, Helm.

---

## Reliability

### REL-01: No resource requests or limits
**File:** `helm/skybyte-app/templates/deployment.yaml`
**What's wrong:** No `resources` block defined
**Why it matters:** Pod can consume all node CPU/memory, starving
other workloads. Kubernetes scheduler cannot make good placement
decisions without requests.
**Fix:** Added requests (cpu: 100m, memory: 128Mi) and limits
(cpu: 500m, memory: 256Mi).

---

### REL-02: Probes pointing to wrong endpoint
**File:** `helm/skybyte-app/templates/deployment.yaml`
**What's wrong:** Both `livenessProbe` and `readinessProbe` point
to `/` instead of `/healthz`
**Why it matters:** `/` is a business endpoint, not a health check.
If the app is overloaded, `/` may be slow but the app is still
technically alive. `/healthz` is the correct dedicated endpoint.
**Fix:** Changed both probes to use `/healthz`.

---

### REL-03: Probes have no thresholds
**File:** `helm/skybyte-app/templates/deployment.yaml`
**What's wrong:** No `initialDelaySeconds`, `periodSeconds`,
`failureThreshold`, or `timeoutSeconds` defined
**Why it matters:** Kubernetes uses defaults which may not match
the app's startup time, causing premature restarts or slow
failure detection.
**Fix:** Added sensible thresholds — liveness: initialDelay 10s,
period 15s, failure 3. Readiness: initialDelay 5s, period 10s,
failure 2.

---

### REL-04: No SIGTERM handler
**File:** `app/main.py`
**What's wrong:** No `signal.signal(signal.SIGTERM, ...)` handler
**Why it matters:** When Kubernetes terminates a pod, it sends
SIGTERM. Without a handler, the app dies immediately, dropping
any in-flight requests.
**Fix:** Added SIGTERM handler that sets a shutdown event,
returning 503 for new requests while existing ones drain.

---

### REL-05: Flask development server in production
**File:** `app/main.py`
**What's wrong:** `app.run()` uses Flask's built-in dev server
**Why it matters:** Flask dev server is single-threaded, not
designed for production traffic, and prints a warning saying so.
**Fix:** Added gunicorn to requirements.txt and CMD in Dockerfile.

---

### REL-06: setup.sh has no error handling
**File:** `setup.sh`
**What's wrong:** No `set -euo pipefail` — script continues even
if docker build or terraform apply fails
**Why it matters:** A failed step is silently ignored, subsequent
steps run against a broken state, making debugging very hard.
**Fix:** Added `set -euo pipefail` as first line.

---

### REL-07: Helm install has no --wait flag
**File:** `setup.sh`
**What's wrong:** `helm upgrade --install` returns immediately
without waiting for pods to be healthy
**Why it matters:** Script reports success before the app is
actually running, masking deployment failures.
**Fix:** Added `--wait --timeout 120s` flags.

---

## Hygiene

### HYG-01: CI lints nothing
**File:** `.github/workflows/ci.yml`
**What's wrong:** `flake8 app/ --exclude=app/* --exit-zero` —
excludes everything it should lint AND uses --exit-zero so it
never fails
**Why it matters:** CI reports green while performing zero
validation. This is worse than no CI because it creates false
confidence.
**Fix:** Replaced with `ruff check app/` which actually lints.

---

### HYG-02: CI swallows all errors
**File:** `.github/workflows/ci.yml`
**What's wrong:** `helm lint || true` and
`terraform validate || true` — errors are swallowed
**Why it matters:** Broken Helm charts and invalid Terraform
will pass CI silently.
**Fix:** Removed `|| true` from all steps. Added kubeconform
for manifest validation and trivy for image scanning.

---

### HYG-03: No unit tests in CI
**File:** `.github/workflows/ci.yml`
**What's wrong:** No test step anywhere in the pipeline
**Why it matters:** Code changes that break endpoints ship
without any automated detection.
**Fix:** Added pytest job running tests against all endpoints
including /metrics.

---

### HYG-04: No .dockerignore
**File:** missing
**What's wrong:** No `.dockerignore` file exists
**Why it matters:** Entire repo including .git, terraform state,
and secrets are sent to Docker build context, slowing builds
and risking secret leakage into image layers.
**Fix:** Added `.dockerignore` excluding git, terraform, docs,
and test files.

---

### HYG-05: Terraform secret has default value
**File:** `terraform/variables.tf`
**What's wrong:** `api_token` variable has a default value
containing the real secret
**Why it matters:** Anyone running terraform apply without
setting TF_VAR_api_token gets the production secret applied
silently.
**Fix:** Removed default, added sensitive = true.

---

## Documentation

### DOC-01: Terraform creates secret but Helm never uses it
**File:** `terraform/main.tf` vs `helm/templates/deployment.yaml`
**What's wrong:** Terraform creates a `kubernetes_secret`
resource called `api-token` but the Helm deployment reads
`apiToken` directly from values.yaml instead
**Why it matters:** The secret management looks correct at
first glance but is completely bypassed. The k8s secret
exists but is unused.
**Fix:** Updated deployment.yaml to use `secretKeyRef`
referencing the Terraform-created secret.

---

### DOC-02: README is outdated
**File:** `README.md`
**What's wrong:** README does not reflect actual setup steps,
ports, or current architecture
**Why it matters:** New engineers following the README will
get a broken setup.
**Fix:** README updated with correct prerequisites, SLO
statement, and setup instructions.

---

### DOC-03: healthz is a stub
**File:** `app/main.py`
**What's wrong:** `# TODO: actually check something useful`
comment in healthz endpoint
**Why it matters:** Probes pass even if the app is in a
broken state, giving false health signals to Kubernetes.
**Fix:** Added shutdown state check to healthz so it returns
503 during graceful shutdown.
