# Manual Cloud Deployment Steps

Cloud deployment was not performed automatically because it requires Fly.io authentication, billing approval, app ownership, secrets, and explicit permission to create resources.

## Prerequisites

1. Install `flyctl`.
2. Run `flyctl auth login`.
3. Choose or confirm app name: `factory-control-owner-test`.
4. Rotate Gemini API key if it was ever exposed.
5. Set production secrets.

## Set Secrets

Copy and edit the example:

```bash
cp scripts/set_fly_secrets.sh.example /tmp/set_factory_fly_secrets.sh
chmod +x /tmp/set_factory_fly_secrets.sh
/tmp/set_factory_fly_secrets.sh factory-control-owner-test
```

Never commit the edited file.

## Deploy

```bash
scripts/deploy_fly.sh factory-control-owner-test
```

The script checks app existence, required secrets, persistent volume, deploys, and verifies `/health`.

## Required CORS Values

For Android cloud testing:

```text
["capacitor://localhost","https://factory-control-owner-test.fly.dev"]
```

For local browser development:

```text
["http://127.0.0.1:5173","http://localhost:5173","capacitor://localhost"]
```

## After Deployment

Run:

```bash
FACTORY_BASE_URL=https://factory-control-owner-test.fly.dev \
OWNER_EMAIL=owner@example.com \
OWNER_PASSWORD='set-securely' \
scripts/smoke_test_deployment.py
```
