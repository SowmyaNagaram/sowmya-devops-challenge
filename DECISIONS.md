# Decisions Log — Skybyte DevOps Challenge

Every meaningful choice made during this exercise is documented
below in the required format.

---

### Decision: Base image selection
**Context:** The starter Dockerfile used `FROM python:3.9` — unpinned,
not minimal, and an older Python version.

**Options considered:**
- `python:3.11` — updated but still full fat image, ~900MB
- `python:3.11-slim` — same Python, stripped to ~130MB, no build tools
- `gcr.io/distroless/python3` — minimal, no shell, harder to debug

**Chosen:** `python:3.11-slim`

**Rationale:** Distroless would be ideal for security but makes
debugging in production much harder — no shell means no kubectl exec
for troubleshooting. slim gives us 85% of the attack surface reduction
with full debuggability. For a challenge with a live system-checks.sh
that uses kubectl exec, distroless would break our own checks.

**Cost / risk you accepted:** Not as minimal as distroless. We accept
this because debuggability during the live walkthrough is a real
constraint.

---

### Decision: Secret management approach
**Context:** The starter repo had the production secret in three places:
values.yaml, variables.tf default, and flowing through as a plain env var.

**Options considered:**
- External Secrets Operator (ESO) — pulls secrets from AWS SSM/Vault,
  best for production but requires an additional operator install
- Sealed Secrets — encrypts secrets for git storage, requires
  controller install and key management
- Terraform kubernetes_secret — creates k8s Secret via Terraform,
  secret passed via TF_VAR environment variable, no additional operators

**Chosen:** Terraform `kubernetes_secret` with `sensitive = true`,
secret passed via `TF_VAR_api_token`

**Rationale:** ESO and Sealed Secrets both require additional cluster
operators that are out of scope for this challenge. The Terraform
approach keeps the footprint small while removing the secret from git
entirely. The secret never touches a file — only a terminal environment
variable.

**Cost / risk you accepted:** TF_VAR_api_token must be set manually
before running terraform apply. In a real team, this would be stored
in CI secrets (GitHub Actions secrets) and injected at pipeline runtime.

---

### Decision: Python linter choice
**Context:** The starter CI used flake8 but configured it to lint
nothing with --exclude=app/* --exit-zero.

**Options considered:**
- `flake8` — established, widely used, but slower and requires
  separate plugins for additional rules
- `ruff` — written in Rust, 10-100x faster than flake8, implements
  flake8 rules plus many more, single binary

**Chosen:** `ruff`

**Rationale:** ruff is a strict superset of flake8's ruleset and
significantly faster in CI. Since we're replacing a broken flake8
config anyway, there's no migration cost. Speed matters in CI
pipelines that run on every push.

**Cost / risk you accepted:** ruff is newer than flake8 — some teams
may be unfamiliar with it. We accept this as the trade-off for better
performance and a more modern toolchain.

---

### Decision: Prometheus scrape strategy
**Context:** The app needed a /metrics endpoint discoverable by
Prometheus.

**Options considered:**
- `ServiceMonitor` CRD — requires Prometheus Operator installed in
  cluster, more powerful and production-grade
- Pod/Service annotations — works with any standard Prometheus install,
  no additional CRDs required

**Chosen:** Prometheus scrape annotations on both Service and Pod
template

**Rationale:** ServiceMonitor requires the Prometheus Operator CRD to
be installed. Since this challenge runs on a local Minikube/Kind
cluster without Prometheus Operator, annotations are the correct
choice. Adding a ServiceMonitor that can never be applied would be
worse than no monitoring at all.

**Cost / risk you accepted:** Annotations are less flexible than
ServiceMonitor — you cannot set scrape intervals or relabeling rules
per-service. In a production cluster with Prometheus Operator, we
would migrate to ServiceMonitor.

---

### Decision: Kyverno over Gatekeeper
**Context:** We needed policy-as-code to enforce security baselines
and catch regressions.

**Options considered:**
- `Gatekeeper` (OPA) — mature, uses Rego language, very expressive
  but steep learning curve
- `Kyverno` — Kubernetes-native, policies written in YAML, easier
  to read and maintain for teams already familiar with k8s manifests

**Chosen:** Kyverno

**Rationale:** The team is already working with Helm and YAML-heavy
tooling. Kyverno policies look like Kubernetes manifests, reducing
cognitive overhead. Rego's expressivity is not needed for the two
policies we're enforcing here — simple pattern matching is sufficient.
Kyverno also has a CLI (kyverno apply) that integrates cleanly into
CI without a running cluster.

**Cost / risk you accepted:** We lose Rego's expressivity for complex
policies. If future policies require cross-resource validation or
complex logic, Gatekeeper would be a better fit.

---

### Decision: Probe thresholds
**Context:** The starter probes had no thresholds defined at all,
relying on Kubernetes defaults which are not appropriate for this app.

**Options considered:**
- Kubernetes defaults: initialDelaySeconds=0, periodSeconds=10,
  failureThreshold=3 — too aggressive for startup
- Conservative: initialDelaySeconds=30 — too slow, delays rollouts
- Tuned: based on observed Python/gunicorn startup time of ~2-3s

**Chosen:**
- Liveness: initialDelay=10s, period=15s, failureThreshold=3
- Readiness: initialDelay=5s, period=10s, failureThreshold=2

**Rationale:** Python with gunicorn starts in under 3 seconds in
testing. 5s readiness initial delay gives 2x headroom without
delaying rollouts. Liveness is more conservative at 10s to avoid
killing a slow-starting pod. failureThreshold=2 on readiness means
we pull the pod from rotation after 20s of failed checks — fast
enough to protect users.

**Cost / risk you accepted:** If the app starts slower in a resource-
constrained environment, these thresholds may cause premature
restarts. We would tune them based on p99 startup time in production.

---

### Decision: Resource limits sizing
**Context:** The starter deployment had no resource requests or limits
at all, making it impossible for the scheduler to place pods correctly.

**Options considered:**
- Very small: cpu=50m/100m, memory=64Mi/128Mi — too tight, risks OOMKill
- Medium: cpu=100m/500m, memory=128Mi/256Mi — matches observed idle usage
- Large: cpu=500m/1000m, memory=256Mi/512Mi — wasteful for a greeting service

**Chosen:** requests: cpu=100m, memory=128Mi / limits: cpu=500m, memory=256Mi

**Rationale:** A Flask/gunicorn greeting service with 2 workers idles
at ~50m CPU and ~80MB memory in testing. We set requests at 2x idle
to give the scheduler accurate placement data with headroom. Limits
are set at 5x requests to allow burst without being wasteful. The
namespace ResourceQuota of 512Mi memory provides a hard ceiling.

**Cost / risk you accepted:** Limits are estimates without load testing.
In production we would run k6 or locust to establish a real baseline
before setting limits.

---

### Decision: terminationGracePeriodSeconds value
**Context:** Kubernetes needs to know how long to wait after sending
SIGTERM before force-killing the pod.

**Options considered:**
- 10s — too short if requests take longer than a few seconds
- 30s — matches gunicorn's --graceful-timeout of 20s with 10s buffer
- 60s — unnecessarily long for a simple greeting service

**Chosen:** 30s with gunicorn --graceful-timeout=20s

**Rationale:** gunicorn's graceful timeout (20s) must be less than
terminationGracePeriodSeconds (30s). This gives gunicorn 20s to
finish in-flight requests, then Kubernetes waits an additional 10s
before force-killing. For a greeting service with sub-100ms response
times, 20s is more than sufficient to drain all requests.

**Cost / risk you accepted:** If a request somehow takes longer than
20s (e.g. a downstream timeout), it will be dropped. We accept this
as the trade-off for predictable pod shutdown times.

---

### Decision: CI pipeline structure
**Context:** The starter CI had a single job that appeared to validate
everything but actually validated nothing.

**Options considered:**
- Single job — simpler but all steps run sequentially, slower feedback
- Multiple parallel jobs — faster feedback, each concern isolated,
  failures are immediately obvious by job name

**Chosen:** Multiple parallel jobs: lint-python, test-python,
helm-validate, terraform-validate, docker-build-scan, kyverno-policy-check

**Rationale:** Parallel jobs give faster feedback and make it obvious
which concern failed. A developer breaking Helm templates doesn't need
to wait for Python tests to finish to see their error. Each job is
independently re-runnable.

**Cost / risk you accepted:** More complex CI configuration. Each job
has its own setup overhead, making total CI runner-minutes higher than
a single sequential job. We accept this for faster developer feedback.

---

### Decision: Kyverno policy rejection evidence

During testing, applying the original deployment.yaml (before fixes)
against our policies produced the following rejection:

---

### Decision: Handling unfixable base-image CVEs
**Context:** Trivy image scan flagged 9 vulnerabilities in
python:3.11-slim, including CRITICAL/HIGH findings in perl-base and
ncurses. These are transitive OS packages pulled in by the base image,
not dependencies our app uses directly.

**Options considered:**
- Switch to distroless to eliminate perl/ncurses entirely — but
  breaks kubectl exec debuggability (see earlier decision)
- Block the pipeline until Debian ships a fix — but several of these
  show `fix_deferred`/`affected` status, meaning no fix exists yet
- Patch what's fixable (pip/setuptools/wheel via upgrade), suppress
  the rest via .trivyignore with documented justification

**Chosen:** Patch fixable findings, suppress unfixable upstream CVEs
with .trivyignore

**Rationale:** wheel and jaraco.context CVEs were fixed by upgrading
pip/setuptools/wheel in the Dockerfile. The remaining perl/ncurses
CVEs have no upstream fix from Debian as of the scan date — these
packages are OS-level dependencies of the base image, not invoked by
our application code, so the actual exploitability is low. Blocking
the entire CI pipeline indefinitely on CVEs with no available patch
would mean the build can never go green through no fault of our own.

**Cost / risk you accepted:** We are running an image with known
unpatched OS-level CVEs in perl/ncurses, mitigated by the fact that
our app never invokes perl and runs as non-root with
readOnlyRootFilesystem, limiting exploitability. We would re-run
trivy weekly via a scheduled CI job to catch when Debian ships fixes.
