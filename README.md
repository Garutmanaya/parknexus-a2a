# ParkNexus A2A

ParkNexus A2A is a production-oriented multi-agent parking reservation platform.

It demonstrates:

- Provider-owned PostgreSQL databases
- Config-driven provider agents
- A2A Agent Cards with skill schemas
- Secure signed A2A calls over HTTPS
- Registry Agent discovery
- Host Agent natural-language orchestration with LangGraph
- Provider-specific schema mapping and validation
- Parallel provider search with synchronous aggregation
- Pricing-aware search
- Slot hold / confirm / cancel / release workflow
- Persistent platform user accounts and transaction history
- React visual parking console with admin user management

## Architecture

```text
React UI
  ↓ HTTPS REST
Host Agent
  ↓ signed A2A
Registry Agent
  ↓ Agent Card discovery
Provider Agents
  ↓
Provider-owned PostgreSQL databases
```

The UI only talks to the Host Agent. Provider URLs and A2A secrets never belong in the browser.

## Quick Start

```bash
cp .env.example .env
./scripts/create_local_certs.sh
./scripts/start_postgres.sh
```

If upgrading from an older provider schema:

```bash
./scripts/reset_provider_dbs.sh
```

Start services in separate terminals:

```bash
./scripts/start_provider_a.sh
./scripts/start_provider_b.sh
./scripts/start_registry.sh
./scripts/start_host.sh
./scripts/start_ui.sh
```

Register providers:

```bash
curl -k -X POST https://localhost:8020/agents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_base_url":"https://localhost:8011"}'

curl -k -X POST https://localhost:8020/agents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_base_url":"https://localhost:8012"}'
```

Open UI:

```text
http://localhost:5173
```

For browser self-signed certificate acceptance, open this once and accept the warning:

```text
https://localhost:8030/health
```

## Admin UI

Default local admin credentials are configured in `.env`:

```env
PARKNEXUS_ADMIN_USER=admin
PARKNEXUS_ADMIN_PASSWORD=admin123
```

The Admin panel in the UI can create/activate users.

## Test Commands

```bash
./scripts/test_curl_commands.sh
```

## Important Environment Variables

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
PLATFORM_DB_NAME=parknexus_platform
A2A_SHARED_SECRET=change_me_shared_hmac_secret
HOST_AGENT_TOKEN=change_me_host_token
REGISTRY_AGENT_TOKEN=change_me_registry_token
LOCAL_TLS_VERIFY=false
OPENAI_API_KEY=change_me
HOST_INTENT_MODEL=gpt-4.1-mini
LOG_DIR=./logs
LOG_LEVEL=INFO
```

## Notes

- `.env` and cert private keys must never be committed.
- Provider Agent Cards publish skill schemas used by the Host Agent for provider-specific payload validation.
- Platform DB stores user accounts and user-facing transactions.
- Provider DBs store actual slot/reservation state.

## Demo all-in-one Docker image

This project includes a demo-only Docker image that runs PostgreSQL, Provider A, Provider B, Registry, Host Agent, and the React UI in one container.

This is intended for demos only. PostgreSQL data is ephemeral and is initialized on container startup.

Build:

```bash
./scripts/build_demo_image.sh
```

Run locally:

```bash
# Optional: pass OPENAI_API_KEY for Host Agent intent parsing
export OPENAI_API_KEY=your_key_here
./scripts/run_demo_local.sh
```

Open the UI:

```text
http://localhost:8080
```

Default demo credentials:

```text
Admin: admin / admin123
User:  demo / demo123
```

Smoke test:

```bash
./scripts/test_demo_container.sh
```

Useful logs:

```bash
docker exec -it parknexus-a2a-demo bash
ls -l /app/logs
tail -f /app/logs/host.stdout.log
```

Exposed demo ports:

```text
8080  UI through Nginx
8030  Host Agent HTTPS
8020  Registry Agent HTTPS
8011  Provider A HTTPS
8012  Provider B HTTPS
```

For cloud demo deployment, expose only port `8080` publicly and keep the agent ports private when possible.

## Demo all-in-one Docker deployment

This demo image runs PostgreSQL, Provider A, Provider B, Registry Agent, Host Agent, and the React UI in one container. PostgreSQL is ephemeral and reinitialized when the container filesystem is recreated.

Create a local runtime env file from the example:

```bash
cp .env.demo.example .env.demo
```

Do not put sensitive secrets in the image. Pass runtime secrets through the env file or shell environment. For OpenAI, prefer:

```bash
export OPENAI_API_KEY=your_key_here
```

Build and run:

```bash
./scripts/build_demo_image.sh
./scripts/run_demo_local.sh
```

Open the UI:

```text
http://localhost:8080
```

Admin login defaults are configured in `.env.demo`. Demo user is auto-created by `docker/register_providers.sh`.

Health dashboard:

```bash
curl -k https://localhost:8030/system/status
```
