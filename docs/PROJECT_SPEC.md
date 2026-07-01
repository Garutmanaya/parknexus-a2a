# ParkNexus A2A — Requirements and Build Specification

## 1. Project Purpose

ParkNexus A2A is a demo-grade but production-inspired multi-agent parking reservation platform.

The system demonstrates:

* Agent-to-agent communication
* Host Agent orchestration
* Registry-based provider discovery
* Independent parking provider agents
* Separate database per provider
* Visual parking garage UI
* User/admin portals
* Secure A2A request signing
* Config-driven startup
* Single-container demo deployment

The platform must be designed so it can run locally, in a single Docker demo image, or later as separate cloud services.

---

## 2. Core Architecture

Required runtime components:

```text
React UI
  ↓
Host Agent
  ↓
Registry Agent
  ↓
Provider Agent A
Provider Agent B
  ↓
Separate PostgreSQL databases per provider
```

The UI must communicate only with the Host Agent.

The UI must never call Provider Agents or Registry Agent directly.

Provider URLs are internal implementation details.

---

## 3. Required Directory Structure

```text
parknexus-a2a/
├── agents/
│   ├── company_a/
│   │   ├── agent.yaml
│   │   └── a2a.yaml
│   └── company_b/
│       ├── agent.yaml
│       └── a2a.yaml
│
├── agent_runtime/
│   ├── api.py
│   ├── bootstrap.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── run.py
│   ├── seed.py
│   └── service.py
│
├── platform_services/
│   ├── host_agent/
│   └── registry_agent/
│
├── shared/
│   ├── config/
│   ├── logging/
│   └── security/
│
├── ui/
│   ├── package.json
│   ├── package-lock.json
│   └── src/
│
├── docker/
│   ├── entrypoint-demo.sh
│   ├── nginx.conf
│   ├── register_providers.sh
│   ├── start-postgres.sh
│   └── supervisord.conf
│
├── scripts/
├── docs/
├── Dockerfile.demo
├── .env.demo.example
├── README.md
└── CLAUDE.md
```

---

## 4. Configuration Requirements

No hardcoded credentials, URLs, ports, database names, or tokens inside service code.

All runtime configuration must come from:

```text
.env
.env.demo
agent.yaml
a2a.yaml
Docker runtime environment variables
Cloud secrets later
```

Required shared config modules:

```text
shared/config/env.py
shared/config/runtime.py
shared/config/security.py
```

Required environment values:

```env
POSTGRES_ADMIN_USER=
POSTGRES_ADMIN_PASSWORD=

HOST_AGENT_ID=
HOST_AGENT_TOKEN=
REGISTRY_AGENT_ID=
REGISTRY_AGENT_TOKEN=
A2A_SHARED_SECRET=

REGISTRY_AGENT_BASE_URL=
HOST_AGENT_BASE_URL=
LOCAL_TLS_VERIFY=

OPENAI_API_KEY=
HOST_INTENT_MODEL=

LOG_DIR=
LOG_LEVEL=

ADMIN_USERNAME=
ADMIN_PASSWORD=
```

For demo Docker, secrets must be passed using:

```bash
docker run --env-file .env.demo ...
```

Do not bake real `.env` files into the image.

---

## 5. Logging Requirements

Use Python built-in `logging`.

All modules must use:

```python
from shared.logging.logger import get_logger

logger = get_logger(__name__)
```

Required log levels:

```text
INFO     business events
DEBUG    request payloads, search parameters, hold IDs, reservation IDs
WARNING  recoverable unexpected conditions
ERROR    exceptions with exc_info=True
CRITICAL service startup failures
```

Log files must be written under:

```text
LOG_DIR=./logs
```

Required logging coverage:

```text
Startup
DB bootstrap
DB seed
Agent registration
Agent discovery
A2A request received
A2A security validation
Host intent parsing
Provider search
Pricing calculation
Slot hold
Reservation confirmation
Hold cancellation
Slot release
User login
Admin login
User creation/update/delete
System health check
```

Do not log:

```text
Authorization headers
Bearer tokens
HMAC secrets
Raw passwords
OpenAI API keys
Private keys
```

---

## 6. Database Requirements

PostgreSQL is required.

Each provider must have a separate database.

Example:

```text
parknexus_platform
parknexus_company_a
parknexus_company_b
```

Provider agents must own their own database schema.

Host Agent and Registry Agent must use platform database only.

Provider database must store:

```text
garages
parking_slots
slot_holds
reservations
slot_events
```

Platform database must store:

```text
registered_agents
users
user_transactions
admin metadata if needed
```

Provider agents must initialize and seed their own DB on startup.

For demo Docker, PostgreSQL is ephemeral and can be recreated on every container startup.

---

## 7. Provider Agent Requirements

Each provider must be fully config-driven.

Provider config files:

```text
agents/<provider>/agent.yaml
agents/<provider>/a2a.yaml
```

Each provider must support independent:

```text
database name
database user
database password
garage layout
levels
rows
slot count
pricing
agent card metadata
A2A skills
```

Provider agents must expose:

```text
/health
/.well-known/agent.json
/.well-known/agent-card.json
/a2a
/a2a/stream
```

Required A2A methods:

```text
search_slots
get_garage_layout
hold_slot
confirm_reservation
cancel_hold
release_slot
```

Provider Agent Cards must expose skill schemas.

Each skill should include:

```json
{
  "id": "search_slots",
  "input_schema": {},
  "output_schema": {}
}
```

---

## 8. Registry Agent Requirements

Registry Agent must be a full A2A agent.

Required endpoints:

```text
/health
/.well-known/agent.json
/.well-known/agent-card.json
/a2a
/a2a/stream
```

Required methods:

```text
register_agent
discover_agents
list_agents
```

Registry must store:

```text
agent name
agent URL
description
provider metadata
capabilities
skills
input/output schemas
active status
created_at
updated_at
```

Provider registration should be idempotent.

In demo Docker, provider registration must happen automatically through deployment orchestration script, not provider startup code.

---

## 9. Host Agent Requirements

Host Agent is the only public API boundary for the UI.

Host Agent responsibilities:

```text
User login
Admin login
User management
Provider discovery
Natural language parsing
Schema mapping
Provider-specific A2A calls
Parallel provider search
Ranking
Garage layout proxy
Hold workflow
Reservation workflow
Cancellation workflow
Transaction persistence
System health dashboard
```

Host Agent must expose:

```text
/health
/system/status
/providers
/parking/chat
/parking/find
/garage/layout
/parking/hold
/parking/confirm
/parking/hold/cancel
/parking/release
/admin/*
/users/*
/transactions/*
```

Host Agent must use Registry A2A to discover providers.

Host Agent must use Provider A2A to perform operations.

---

## 10. Agent Communication Requirements

All agent-to-agent calls must use secure A2A JSON-RPC.

Required headers:

```text
Authorization: Bearer <token>
X-Agent-Id
X-Request-Id
X-Timestamp
X-Signature
```

Signature payload:

```text
agent_id + request_id + timestamp + exact request body
```

Use HMAC SHA256 for local/demo security.

Validate:

```text
bearer token
agent ID
timestamp skew
HMAC signature
```

Future security upgrade:

```text
PKI
signed Agent Cards
mTLS
per-agent public keys
trust registry
```

---

## 11. LLM / AI Requirements

Provider Agents do not receive raw natural language.

Flow:

```text
User natural language
  ↓
Host Agent LLM intent parser
  ↓
Validated structured intent
  ↓
Provider-specific schema mapper
  ↓
Validated A2A request
  ↓
Provider Agent
```

LLM must be used only in Host Agent.

LLM must output structured data validated by Pydantic.

Provider schema mapping must use Agent Card schema metadata.

If validation fails, Host Agent must not call provider.

---

## 12. Pricing Requirements

Provider owns pricing logic.

Host parses user budget intent but does not fake provider pricing.

Provider must support:

```text
hourly_rate
daily_rate
monthly_rate
estimated_price
estimated_price_unit
```

Remove duplicate legacy fields later:

```text
price_per_hour
```

Provider must calculate estimated price based on:

```text
budget_amount
budget_unit
duration_minutes
pricing rules
```

---

## 13. UI Requirements

UI must be chat-first.

Required portals:

```text
/admin
/app
```

Admin UI:

```text
Admin login
Create user
Update user
Delete/disable user
Agent management
Environment health dashboard
```

User UI:

```text
User login
Chat box
Provider summary
Recommended slots
Visual garage layout
Slot selection
Hold
Confirm hold
Reserve directly
Cancel/release from history
Last 5 transaction history
```

UI must call Host Agent only.

UI must not expose Provider Agent URLs to the user.

UI must clear right-side provider/layout display when search returns zero results.

Hold → confirm flow must be visible from transaction history.

---

## 14. Docker Demo Requirements

Single demo Docker image must run:

```text
PostgreSQL
Provider A
Provider B
Registry Agent
Host Agent
Nginx
React UI
```

Use `supervisord` to run multiple services.

PostgreSQL may be ephemeral.

Demo image must not contain real secrets.

Runtime env file:

```bash
docker run --env-file .env.demo ...
```

Dockerfile must use deterministic dependencies.

UI dependencies must be pinned.

Do not use `latest` in `package.json`.

Keep `package-lock.json`.

Docker build should use:

```dockerfile
RUN npm ci --no-audit --no-fund
```

---

## 15. Script Requirements

Required scripts:

```text
scripts/build_demo_image.sh
scripts/run_demo_local.sh
scripts/test_demo_container.sh
scripts/create_local_certs.sh
scripts/reset_provider_dbs.sh
scripts/reset_platform_db.sh
scripts/start_provider_a.sh
scripts/start_provider_b.sh
scripts/start_registry.sh
scripts/start_host.sh
scripts/start_ui.sh
```

Demo startup must:

```text
start PostgreSQL
start providers
start registry
start host
start UI/nginx
auto-register providers after health checks
```

---

## 16. System Health Requirements

Host must expose:

```text
GET /system/status
```

Must report:

```text
PostgreSQL
Host Agent
Registry Agent
Provider A
Provider B
UI/Nginx
```

Admin UI must display health cards with status indicators.

---

## 17. Current Stable Milestone Summary

Implemented milestone includes:

```text
Multi-agent parking system
Provider-specific databases
Registry A2A discovery
Secure A2A calls
LangGraph Host Agent
Natural language search
Provider schema mapping
Parallel provider search
User/admin login
User management
Transaction history
Visual parking garage UI
Hold/confirm/cancel/release
Single Docker demo image
Auto DB bootstrap
Auto provider registration
Logging framework
Admin health dashboard
```

---

## 18. Future Requirements

Recommended next improvements:

```text
1. PKI-based agent trust
2. Signed Agent Cards
3. mTLS for cloud service-to-service traffic
4. Replay protection with request ID cache
5. Per-agent authorization policies
6. Payment Agent
7. Stripe Connect-style provider payout flow
8. Email/SMS notification service
9. Hold expiration alerts
10. WebSocket/SSE live garage updates
11. Observability with OpenTelemetry/Langfuse/LangSmith
12. AWS ECS deployment
13. ALB HTTPS
14. Secrets Manager
15. RDS PostgreSQL for production mode
16. CI/CD pipeline
17. Provider onboarding workflow
18. More provider-specific schemas
19. Advanced LLM planning
20. Multi-agent negotiation / pricing optimization
```

---

## 19. Non-Negotiable Design Rules

```text
UI talks only to Host Agent.
Provider Agents own their databases.
Host Agent never directly reads provider databases.
Registry discovers agents through Agent Cards.
Agent Card must declare capabilities and schemas.
A2A calls must be signed.
All runtime config must be externalized.
No secrets in Docker images.
No hardcoded localhost URLs in service code.
Logging must exist at every service boundary.
Provider registration belongs to deployment orchestration, not provider startup.
```

