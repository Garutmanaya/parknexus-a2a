# ParkNexus A2A Design Document

## Purpose

ParkNexus A2A is a production-oriented multi-agent parking reservation platform. It demonstrates provider-owned databases, A2A Agent Cards, secure signed agent-to-agent calls, natural-language Host Agent orchestration, and a visual parking console.

## Core Requirements

1. Each parking provider runs independently from configuration.
2. Each provider owns its own PostgreSQL database, user, and credentials.
3. Provider agents expose A2A discovery and task endpoints.
4. Registry Agent discovers and persists provider Agent Cards.
5. Host Agent accepts natural language, parses structured intent with an LLM, discovers providers, calls providers over secure A2A, ranks results, and manages hold/confirm/cancel/release workflows.
6. All local agent endpoints run over HTTPS.
7. A2A calls require bearer token plus HMAC signature headers.
8. File-based logging records API calls, A2A calls, security checks, searches, holds, confirmations, cancellations, and errors.
9. Visual UI shows garage levels, rows, slot status, pricing, and booking actions.

## Runtime Components

```text
React UI
  ↓ HTTPS REST
Host Agent
  ↓ signed A2A
Registry Agent
  ↓ HTTPS Agent Card fetch
Provider Agents
  ↓
Provider-owned PostgreSQL databases
```

## Provider Agent

The provider runtime is generic. A provider is created by `agent.yaml` and `a2a.yaml`.

Responsibilities:

- bootstrap provider DB/user
- create ORM tables
- seed garage layout
- expose Agent Card
- search slots
- calculate pricing
- hold slot
- confirm reservation
- cancel hold
- release slot
- return garage layout for UI

## Registry Agent

The Registry Agent stores provider Agent Cards in the platform DB.

Responsibilities:

- register provider base URLs
- fetch provider Agent Cards
- validate capabilities and skills
- discover providers by skill/tag/capability
- expose A2A methods: `register_agent`, `discover_agents`, `list_agents`

## Host Agent

The Host Agent is the AI-facing layer.

Responsibilities:

- parse natural language into `ParkingIntent`
- discover matching providers through Registry A2A
- call provider A2A endpoints
- rank results by price/distance
- orchestrate hold/confirm/cancel/release
- expose visual-console support APIs

## Security

A2A requests use:

```text
Authorization: Bearer <token>
X-Agent-Id: <agent_id>
X-Request-Id: <uuid>
X-Timestamp: <unix_timestamp>
X-Signature: <hmac_sha256>
```

Signature payload:

```text
agent_id.request_id.timestamp.<raw_body>
```

Local TLS uses self-signed certs. Cloud should use ALB/API Gateway TLS and Secrets Manager.

## Pricing Model

Provider owns pricing. Host sends semantic budget information; provider calculates whether a slot matches.

Provider fields:

- hourly_rate
- daily_rate
- monthly_rate

Search inputs:

- budget_amount
- budget_unit: hour, day, month, total
- duration_minutes

Provider response includes:

- estimated_price
- estimated_price_unit

## Visual Console

The UI calls Host Agent APIs:

- `/parking/chat`
- `/garage/layout`
- `/parking/hold`
- `/parking/confirm`
- `/parking/hold/cancel`
- `/parking/release`

Slot statuses:

- AVAILABLE
- HELD
- RESERVED
- OCCUPIED
- BLOCKED
- MAINTENANCE

## Deployment Notes

Local:

- Docker Compose for PostgreSQL
- Python services for Provider A/B, Registry, Host
- Vite React UI

Cloud:

- ECS Fargate or EKS
- RDS PostgreSQL
- ALB HTTPS
- Secrets Manager
- CloudWatch logs
