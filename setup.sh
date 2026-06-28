#!/usr/bin/env bash
set -euo pipefail

echo "==> Checking required tools..."
command -v docker     >/dev/null 2>&1 || { echo "ERROR: docker not found"; exit 1; }
command -v terraform  >/dev/null 2>&1 || { echo "ERROR: terraform not found"; exit 1; }
command -v helm       >/dev/null 2>&1 || { echo "ERROR: helm not found"; exit 1; }
command -v kubectl    >/dev/null 2>&1 || { echo "ERROR: kubectl not found"; exit 1; }

echo "==> Building Docker image..."
docker build -t skybyte/app:1.0.0 .

echo "==> Applying Terraform..."
cd terraform
terraform init -upgrade
terraform apply -auto-approve
cd ..

echo "==> Installing/upgrading Helm chart..."
helm upgrade --install skybyte-app helm/skybyte-app \
  --namespace devops-challenge \
  --create-namespace \
  --wait \
  --timeout 120s

echo "==> Verifying rollout..."
kubectl rollout status deployment/skybyte-app \
  --namespace devops-challenge \
  --timeout 60s

echo "==> All steps completed successfully."
