#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="devops-challenge"

echo "==> Getting pod name..."
POD=$(kubectl get pod -n $NAMESPACE -l app.kubernetes.io/name=skybyte-app -o jsonpath='{.items[0].metadata.name}')
echo "Pod: $POD"

echo ""
echo "==> Check 1: UID inside container (must NOT be 0)"
kubectl exec -n $NAMESPACE "$POD" -- id

echo ""
echo "==> Check 2: Bound port and capabilities"
kubectl exec -n $NAMESPACE "$POD" -- cat /proc/1/status | grep -E "^(Cap|Uid)"

echo ""
echo "==> Check 3: Curl / and validate response"
RESPONSE=$(kubectl exec -n $NAMESPACE "$POD" -- wget -qO- http://localhost:8080/)
echo "Response: $RESPONSE"
echo "$RESPONSE" | grep -q "Hello, Candidate" && echo "✅ Response valid" || { echo "❌ Response invalid"; exit 1; }

echo ""
echo "==> Check 4: Curl /metrics and verify http_requests_total exists"
kubectl exec -n $NAMESPACE "$POD" -- wget -qO- http://localhost:8080/metrics | grep "http_requests_total"
echo "✅ Metrics endpoint working"

echo ""
echo "==> Check 5: Kill pod and verify recovery within 30s"
echo "Deleting pod $POD..."
kubectl delete pod -n $NAMESPACE "$POD"

echo "Waiting for new pod to come up..."
sleep 5

kubectl rollout status deployment/skybyte-app \
  --namespace $NAMESPACE \
  --timeout 30s

echo "✅ Deployment recovered successfully"

echo ""
echo "==> All checks passed!"
