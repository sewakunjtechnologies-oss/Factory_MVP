#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${1:-${FLY_APP_NAME:-factory-control-owner-test}}"
REGION="${FLY_REGION:-sin}"
VOLUME_NAME="${FLY_VOLUME_NAME:-factory_data}"
VOLUME_SIZE_GB="${FLY_VOLUME_SIZE_GB:-1}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need flyctl

if ! flyctl auth whoami >/dev/null 2>&1; then
  echo "flyctl is not authenticated. Run: flyctl auth login" >&2
  exit 1
fi

missing=()
for key in SECRET_KEY GEMINI_API_KEY DATABASE_URL REPORT_OUTPUT_DIR CORS_ORIGINS ENVIRONMENT; do
  if ! flyctl secrets list -a "$APP_NAME" 2>/dev/null | awk '{print $1}' | grep -qx "$key"; then
    missing+=("$key")
  fi
done

if ! flyctl apps list 2>/dev/null | awk '{print $1}' | grep -qx "$APP_NAME"; then
  echo "Fly app $APP_NAME does not exist."
  read -r -p "Create app $APP_NAME now? This may require billing. Type yes: " answer
  if [[ "$answer" != "yes" ]]; then
    echo "Aborted before app creation."
    exit 1
  fi
  flyctl apps create "$APP_NAME"
fi

if ((${#missing[@]} > 0)); then
  echo "Missing Fly secrets for $APP_NAME: ${missing[*]}" >&2
  echo "Set them with scripts/set_fly_secrets.sh.example, then rerun."
  exit 1
fi

if ! flyctl volumes list -a "$APP_NAME" 2>/dev/null | awk '{print $1}' | grep -qx "$VOLUME_NAME"; then
  echo "Persistent volume $VOLUME_NAME does not exist for $APP_NAME."
  read -r -p "Create ${VOLUME_SIZE_GB}GB volume in ${REGION}? This may require billing. Type yes: " answer
  if [[ "$answer" != "yes" ]]; then
    echo "Aborted before volume creation."
    exit 1
  fi
  flyctl volumes create "$VOLUME_NAME" --size "$VOLUME_SIZE_GB" --region "$REGION" -a "$APP_NAME"
fi

flyctl deploy -a "$APP_NAME"

URL="https://${APP_NAME}.fly.dev"
echo "Checking $URL/health"
curl -fsS "$URL/health"
echo
echo "Backend URL: $URL"
