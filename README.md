# ParkNexus A2A

ParkNexus A2A is a config-driven multi-agent parking reservation platform.

It includes:

- provider-owned PostgreSQL databases
- FastAPI provider agents
- A2A Agent Cards
- secure signed A2A calls
- Registry Agent discovery
- Host Agent natural-language orchestration
- LangGraph workflow
- pricing-aware search
- reservation lifecycle
- React visual parking console

## Quick Start

Create `.env`:

```bash
cp .env.example .env
```

Create local certs:

```bash
./scripts/create_local_certs.sh
```

Start PostgreSQL:

```bash
./scripts/start_postgres.sh
```

If you are upgrading from an older schema, reset provider DBs first:

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

Run tests manually:

```bash
./scripts/test_curl_commands.sh
```

Open UI:

```text
http://localhost:5173
```

## Main Services

```text
Provider A: https://localhost:8011
Provider B: https://localhost:8012
Registry:   https://localhost:8020
Host:       https://localhost:8030
UI:         http://localhost:5173
```

## Documentation

See:

```text
docs/DESIGN.md
```
